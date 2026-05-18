import asyncio
import io
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import structlog
from piper.voice import PiperVoice

from aura.config import get_config

logger = structlog.get_logger(__name__)


class PiperTTS:
    """
    Text-to-Speech singleton using Piper TTS.
    Provides fast, local voice synthesis with high-quality ONNX models.
    """

    _instance: Optional["PiperTTS"] = None
    _voice: Optional[PiperVoice] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PiperTTS, cls).__new__(cls)
        return cls._instance

    async def _get_voice(self) -> PiperVoice:
        """
        Lazily loads the Piper voice model on first use.
        Expects 'en_US-amy-medium.onnx' and its json config in ~/.aura/tts_models/.
        """
        if self._voice is not None:
            return self._voice

        async with self._lock:
            if self._voice is not None:
                return self._voice

            # Standard Aura model path
            model_dir = Path.home() / ".aura" / "tts_models"
            model_path = model_dir / "en_US-amy-medium.onnx"
            config_path = model_dir / "en_US-amy-medium.onnx.json"

            if not model_path.exists():
                logger.error(
                    "piper_model_missing",
                    path=str(model_path),
                    hint="Download models to ~/.aura/tts_models/",
                )
                raise FileNotFoundError(f"Piper model not found at {model_path}")

            logger.info("loading_piper_tts_model", model="en_US-amy-medium")
            start_time = time.perf_counter()

            try:
                # Load the model in a background thread to avoid blocking the event loop
                self._voice = await asyncio.to_thread(
                    PiperVoice.load, str(model_path), str(config_path)
                )
                latency = time.perf_counter() - start_time
                logger.info("piper_tts_loaded", latency_s=round(latency, 2))
            except Exception as e:
                logger.error("piper_tts_load_failed", error=str(e))
                raise

            return self._voice

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesizes the text and returns raw WAV bytes.
        Runs in a background thread to avoid blocking the event loop.
        """
        if not text.strip():
            return b""

        voice = await self._get_voice()

        def _run_synthesis() -> bytes:
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(voice.config.sample_rate)

                    # Piper yields raw int16 bytes for each chunk
                    for audio_bytes in voice.synthesize(text):
                        wav_file.writeframes(audio_bytes)

                return wav_io.getvalue()

        return await asyncio.to_thread(_run_synthesis)

    async def speak(self, text: str) -> None:
        """
        Synthesizes the text and plays it through sounddevice.
        Both synthesis and playback run in background threads.
        """
        if not text.strip():
            return

        logger.info("tts_speak_start", text_length=len(text))
        start_time = time.perf_counter()

        try:
            # 1. Synthesize to WAV bytes
            wav_bytes = await self.synthesize(text)
            synth_latency = time.perf_counter() - start_time

            # 2. Playback using sounddevice in a background thread
            def _run_playback():
                with io.BytesIO(wav_bytes) as wav_io:
                    with wave.open(wav_io, "rb") as wav_file:
                        sample_rate = wav_file.getframerate()
                        n_frames = wav_file.getnframes()
                        audio_raw = wav_file.readframes(n_frames)

                        # Convert raw bytes to numpy array for sounddevice
                        samples = np.frombuffer(audio_raw, dtype=np.int16)

                        logger.debug(
                            "piper_playback_start",
                            sample_rate=sample_rate,
                            frames=n_frames,
                            synth_latency_s=round(synth_latency, 2),
                        )
                        sd.play(samples, samplerate=sample_rate)
                        sd.wait()

            await asyncio.to_thread(_run_playback)

            total_latency = time.perf_counter() - start_time
            logger.info("tts_speak_completed", total_latency_s=round(total_latency, 2))

        except Exception as e:
            logger.error("tts_speak_failed", error=str(e))


# Alias for compatibility with existing orchestrator and tests
# This can be removed once the rest of the codebase is updated to use PiperTTS
KokoroTTS = PiperTTS
