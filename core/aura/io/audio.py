import asyncio
import io
import wave
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import sounddevice as sd
import structlog

logger = structlog.get_logger()

class AudioRecorder:
    """
    Handles capturing raw audio from the system microphone.
    Configured for 16kHz mono 16-bit PCM, optimized for STT.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.channels = 1
        self.dtype = "int16"
        self._recording: Optional[np.ndarray] = None
        self._stream: Optional[sd.InputStream] = None
        self._frames: list[np.ndarray] = []

    def _callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            logger.warning("audio_stream_status", status=str(status))
        self._frames.append(indata.copy())

    def start_recording(self) -> None:
        """Starts an asynchronous audio capture stream."""
        try:
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._callback
            )
            self._stream.start()
            logger.info("audio_recording_started", sample_rate=self.sample_rate)
        except sd.PortAudioError as e:
            logger.error("audio_device_not_found", error=str(e))
            self._stream = None
        except Exception as e:
            logger.error("audio_start_failed", error=str(e))
            self._stream = None

    def stop_recording(self) -> bytes:
        """
        Stops the stream and returns the captured audio as WAV-formatted bytes.
        Returns empty bytes if no recording was active or failed.
        """
        if not self._stream:
            return b""

        self._stream.stop()
        self._stream.close()
        self._stream = None
        
        if not self._frames:
            return b""

        # Concatenate all captured blocks
        audio_data = np.concatenate(self._frames, axis=0)
        
        # Convert to WAV bytes
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
        
        wav_bytes = buffer.getvalue()
        logger.info("audio_recording_stopped", size_bytes=len(wav_bytes))
        return wav_bytes

@dataclass
class TranscriptionResult:
    text: str = ""

@asynccontextmanager
async def push_to_talk():
    """
    Async context manager that handles the start/stop recording cycle.
    Yields a TranscriptionResult object that will contain the text on exit.
    """
    recorder = AudioRecorder()
    recorder.start_recording()
    result = TranscriptionResult()
    
    try:
        yield result
    finally:
        wav_bytes = recorder.stop_recording()
        
        if not wav_bytes:
            return

        try:
            # Step 3.3 implements WhisperSTT.
            from aura.io.stt import WhisperSTT
            stt = WhisperSTT()
            result.text = await stt.transcribe(wav_bytes)
            logger.info("ptt_transcription_completed", text=result.text)
        except ImportError:
            logger.warning("stt_module_not_found", detail="Step 3.3 not yet implemented")
        except Exception as e:
            logger.error("ptt_transcription_failed", error=str(e))
