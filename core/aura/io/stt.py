import asyncio
import time
from typing import Optional

import numpy as np
import structlog
from faster_whisper import WhisperModel

logger = structlog.get_logger()


class WhisperSTT:
    """
    Speech-to-Text singleton using faster-whisper.
    Optimized for low-latency CPU inference as part of the Advanced Voice Layer.
    """

    _instance: Optional["WhisperSTT"] = None
    _model: Optional[WhisperModel] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperSTT, cls).__new__(cls)
        return cls._instance

    async def _get_model(self) -> WhisperModel:
        """
        Lazily loads the Whisper model on first use.
        Uses whisper-base.en with int8 quantization for speed on CPU.
        """
        if self._model is not None:
            return self._model

        async with self._lock:
            if self._model is not None:
                return self._model

            logger.info("loading_whisper_model", model="base.en", compute_type="int8")
            start_time = time.perf_counter()

            try:
                # Run the model loading in a separate thread to keep the event loop responsive
                self._model = await asyncio.to_thread(
                    WhisperModel, "base.en", device="cpu", compute_type="int8"
                )
                latency = time.perf_counter() - start_time
                logger.info("whisper_model_loaded", latency_s=round(latency, 2))
            except Exception as e:
                logger.error("whisper_model_load_failed", error=str(e))
                raise

            return self._model

    async def transcribe(self, audio_data: np.ndarray) -> str:
        """
        Transcribes the provided audio data (numpy array) to text.

        Args:
            audio_data: np.ndarray containing 16kHz mono audio.

        Returns:
            The transcribed text string.
        """
        if audio_data is None or audio_data.size == 0:
            return ""

        model = await self._get_model()

        start_time = time.perf_counter()
        try:
            # Transcription is CPU-intensive, run in a separate thread.
            # beam_size=1 is the fastest setting (greedy decoding).
            segments, info = await asyncio.to_thread(
                model.transcribe, audio_data, beam_size=1, language="en"
            )

            # segments is a generator; we must consume it to get the results.
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text.strip())

            full_text = " ".join(text_segments).strip()

            latency = time.perf_counter() - start_time
            logger.info(
                "transcription_completed",
                text=full_text,
                latency_s=round(latency, 2),
                probability=round(info.language_probability, 2),
            )

            return full_text

        except Exception as e:
            logger.error("transcription_failed", error=str(e))
            return ""
