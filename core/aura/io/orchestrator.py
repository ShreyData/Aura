import asyncio
import json
from enum import Enum
from typing import Optional

import httpx
import structlog

from aura.config import get_config
from aura.events import get_event_bus
from aura.io.audio import AudioStreamer
from aura.io.stt import WhisperSTT
from aura.io.tts import KokoroTTS
from aura.io.vad import SileroVAD

logger = structlog.get_logger()


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class VoiceOrchestrator:
    """
    Coordinates the advanced voice interaction loop.
    Manages transitions between LISTENING, THINKING, and SPEAKING states.
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.event_bus = get_event_bus()

        # IO Components
        self.audio = AudioStreamer()
        self.vad = SileroVAD()
        self.stt = WhisperSTT()
        self.tts = KokoroTTS()

        self.state = VoiceState.IDLE
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Starts the background voice orchestration loop."""
        if self._task is not None:
            logger.warning("voice_orchestrator_already_running")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("voice_orchestrator_started")

    async def stop(self) -> None:
        """Stops the voice orchestration loop."""
        if self._task is None:
            return

        self._stop_event.set()
        self.audio.stop()
        await self._task
        self._task = None
        await self._set_state(VoiceState.IDLE)
        logger.info("voice_orchestrator_stopped")

    async def _set_state(self, state: VoiceState) -> None:
        """Updates the state and publishes an orb_state event."""
        if self.state == state:
            return

        self.state = state
        logger.info("voice_state_changed", state=state.value)
        await self.event_bus.publish("orb_state", {"state": state.value})

    async def _run_loop(self) -> None:
        """The main orchestration loop."""
        if not self.audio.start():
            logger.error("failed_to_start_audio_streamer")
            return

        # Track silence/speech duration for trigger logic
        speech_detected = False
        silence_start_time = None
        speech_start_time = None

        # Minimum durations for stability
        MIN_SPEECH_MS = 300
        MAX_SILENCE_MS = 800

        await self._set_state(VoiceState.LISTENING)

        try:
            while not self._stop_event.is_set():
                # 1. Get current audio buffer
                # Note: For better VAD we should probably process chunks of 50-100ms
                # but get_buffer() returns the whole 10s. We take the last 100ms chunk.
                full_buffer = self.audio.get_buffer()

                # Sample rate is 16000, 100ms is 1600 samples
                CHUNK_SIZE = 1600
                if len(full_buffer) < CHUNK_SIZE:
                    await asyncio.sleep(0.05)
                    continue

                latest_chunk = full_buffer[-CHUNK_SIZE:]

                # 2. Check for speech
                is_speech = await self.vad.is_speech(latest_chunk.tobytes())

                current_time = asyncio.get_event_loop().time()

                if is_speech:
                    if not speech_detected:
                        speech_detected = True
                        speech_start_time = current_time
                        logger.debug("speech_started")
                    silence_start_time = None
                else:
                    if speech_detected:
                        if silence_start_time is None:
                            silence_start_time = current_time

                        # Check if silence has lasted long enough to trigger STT
                        silence_duration = (current_time - silence_start_time) * 1000
                        speech_duration = (current_time - speech_start_time) * 1000

                        if (
                            silence_duration > MAX_SILENCE_MS
                            and speech_duration > MIN_SPEECH_MS
                        ):
                            logger.info(
                                "speech_finished", duration_ms=round(speech_duration)
                            )
                            await self._process_speech()

                            # Reset for next interaction
                            speech_detected = False
                            silence_start_time = None
                            speech_start_time = None
                            self.audio.clear_buffer()
                            await self._set_state(VoiceState.LISTENING)

                await asyncio.sleep(0.05)  # Poll at 20Hz

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("voice_loop_error", error=str(e))
        finally:
            await self._set_state(VoiceState.IDLE)

    async def _process_speech(self) -> None:
        """
        Executes the THINKING and SPEAKING phases of the loop.
        """
        await self._set_state(VoiceState.THINKING)

        # 1. Get full speech buffer
        audio_data = self.audio.get_buffer()

        # 2. Transcribe
        text = await self.stt.transcribe(audio_data)
        if not text:
            logger.info("no_speech_transcribed")
            return

        logger.info("speech_transcribed", text=text)

        # 3. Call LLM (via local API to reuse tool logic)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                api_url = (
                    f"http://127.0.0.1:{self.config.core_port}/v1/chat/completions"
                )

                # For now, we don't have long-term history passed in here
                # In Phase 5, we'll fetch context from history.py
                request_payload = {
                    "model": self.config.default_model,
                    "messages": [{"role": "user", "content": text}],
                    "stream": True,
                }

                full_response = ""
                async with client.stream(
                    "POST", api_url, json=request_payload
                ) as response:
                    if response.status_code != 200:
                        logger.error("api_call_failed", status=response.status_code)
                        return

                    # 4. Speak response (sentence by sentence for low latency)
                    current_sentence = ""
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        if "[DONE]" in line:
                            break

                        try:
                            chunk = json.loads(line[6:])
                            content = chunk["choices"][0]["delta"].get("content", "")
                            full_response += content
                            current_sentence += content

                            # Simple sentence splitting logic
                            if any(punct in content for punct in [".", "!", "?", "\n"]):
                                if current_sentence.strip():
                                    await self._set_state(VoiceState.SPEAKING)
                                    await self.tts.speak(current_sentence.strip())
                                    await self._set_state(VoiceState.THINKING)
                                    current_sentence = ""
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

                    # Speak remaining fragment
                    if current_sentence.strip():
                        await self._set_state(VoiceState.SPEAKING)
                        await self.tts.speak(current_sentence.strip())

                logger.info("voice_response_completed", response=full_response)

        except Exception as e:
            logger.error("voice_thinking_failed", error=str(e))
