import asyncio
import io
import time
from typing import Optional

import structlog
from faster_whisper import WhisperModel

logger = structlog.get_logger()

class WhisperSTT:
    """
    Singleton class for Speech-to-Text using faster-whisper.
    Lazily loads the model and performs transcription in a separate thread.
    """
    _instance: Optional['WhisperSTT'] = None
    _model: Optional[WhisperModel] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperSTT, cls).__new__(cls)
        return cls._instance

    async def _get_model(self) -> WhisperModel:
        """
        Lazily initializes the Whisper model.
        Uses asyncio.to_thread for the blocking model load.
        """
        if self._model is not None:
            return self._model

        async with self._lock:
            # Re-check inside lock to prevent race conditions
            if self._model is not None:
                return self._model

            logger.info("loading_whisper_model", model="base.en")
            start_time = time.perf_counter()
            
            # Using 'base.en' for high speed and good accuracy for English
            # compute_type="int8" is optimized for CPU inference
            try:
                self._model = await asyncio.to_thread(
                    WhisperModel,
                    "base.en",
                    device="cpu",
                    compute_type="int8"
                )
                latency = time.perf_counter() - start_time
                logger.info("whisper_model_loaded", latency_s=round(latency, 2))
            except Exception as e:
                logger.error("whisper_model_load_failed", error=str(e))
                raise

            return self._model

    async def transcribe(self, wav_bytes: bytes) -> str:
        """
        Transcribes the provided WAV bytes into text.
        Returns the combined text of all segments.
        """
        if not wav_bytes:
            return ""

        model = await self._get_model()
        
        logger.info("starting_transcription", size_bytes=len(wav_bytes))
        start_time = time.perf_counter()

        try:
            # Convert bytes to a file-like object
            audio_file = io.BytesIO(wav_bytes)
            
            # transcription is CPU intensive, run in thread
            # beam_size=5 is standard for good accuracy
            segments, info = await asyncio.to_thread(
                model.transcribe,
                audio_file,
                beam_size=5,
                language="en"
            )

            # segments is a generator, we need to consume it
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text.strip())

            full_text = " ".join(text_segments).strip()
            
            latency = time.perf_counter() - start_time
            logger.info(
                "transcription_completed",
                text=full_text,
                latency_s=round(latency, 2),
                probability=round(info.language_probability, 2)
            )
            
            return full_text

        except Exception as e:
            logger.error("transcription_failed", error=str(e))
            return ""
