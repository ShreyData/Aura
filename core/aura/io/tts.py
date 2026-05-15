import asyncio
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

import numpy as np
import sounddevice as sd
import structlog
from kokoro_onnx import Kokoro

logger = structlog.get_logger()


class KokoroTTS:
    """
    Text-to-Speech singleton using Kokoro ONNX.
    Provides ultra-fast, high-quality local voice synthesis.
    """

    _instance: Optional["KokoroTTS"] = None
    _kokoro: Optional[Kokoro] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KokoroTTS, cls).__new__(cls)
        return cls._instance

    async def _get_kokoro(self) -> Kokoro:
        """
        Lazily initializes the Kokoro engine.
        Expects 'kokoro-v0_19.onnx' and 'voices.json' in ~/.aura/tts_models/.
        """
        if self._kokoro is not None:
            return self._kokoro

        async with self._lock:
            if self._kokoro is not None:
                return self._kokoro

            # Standard Aura model path
            model_dir = Path.home() / ".aura" / "tts_models"
            model_path = model_dir / "kokoro-v0_19.onnx"
            voices_path = model_dir / "voices.json"

            if not model_path.exists() or not voices_path.exists():
                logger.error(
                    "tts_model_missing",
                    model_path=str(model_path),
                    voices_path=str(voices_path),
                    hint="TTS models must be downloaded to ~/.aura/tts_models/",
                )
                # In a real scenario, we might trigger a download here,
                # but for now we raise an error to indicate setup is required.
                raise FileNotFoundError(f"TTS models not found in {model_dir}")

            logger.info("loading_kokoro_tts_model", model="kokoro-v0_19")
            start_time = time.perf_counter()

            try:
                # Load ONNX model and voices inside a thread
                self._kokoro = await asyncio.to_thread(
                    Kokoro, str(model_path), str(voices_path)
                )
                latency = time.perf_counter() - start_time
                logger.info("kokoro_tts_loaded", latency_s=round(latency, 2))
            except Exception as e:
                logger.error("kokoro_tts_load_failed", error=str(e))
                raise

            return self._kokoro

    async def speak(self, text: str, voice: str = "af_sky") -> None:
        """
        Synthesizes text and plays it immediately through the system speakers.
        'af_sky' is a high-quality female voice (equivalent to en-us-amy).
        """
        if not text.strip():
            return

        kokoro = await self._get_kokoro()

        logger.info("tts_speak_start", text_length=len(text), voice=voice)
        start_time = time.perf_counter()

        try:
            # Synthesis is CPU-bound
            samples, sample_rate = await asyncio.to_thread(
                kokoro.create, text, voice=voice, speed=1.0, lang="en-us"
            )

            synth_latency = time.perf_counter() - start_time

            # Playback is I/O bound (waiting for hardware)
            logger.debug("tts_playback_start", synth_latency_s=round(synth_latency, 2))
            await asyncio.to_thread(sd.play, samples, sample_rate)
            await asyncio.to_thread(sd.wait)

            total_latency = time.perf_counter() - start_time
            logger.info("tts_speak_completed", total_latency_s=round(total_latency, 2))

        except Exception as e:
            logger.error("tts_speak_failed", error=str(e))

    async def synthesize(
        self, text: str, voice: str = "af_sky"
    ) -> AsyncGenerator[np.ndarray, None]:
        """
        Streaming synthesis. Yields raw audio chunks as they are generated.
        Useful for long texts or low-latency 'speak-as-you-type' flows.
        """
        if not text.strip():
            return

        kokoro = await self._get_kokoro()

        logger.info("tts_stream_start", text_length=len(text), voice=voice)

        try:
            # Kokoro-onnx provides a generator for chunks
            async for samples, sample_rate in kokoro.create_stream(
                text, voice=voice, speed=1.0, lang="en-us"
            ):
                yield samples
        except Exception as e:
            logger.error("tts_stream_failed", error=str(e))
