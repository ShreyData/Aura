import threading
from collections import deque
from typing import Optional

import numpy as np
import sounddevice as sd
import structlog

logger = structlog.get_logger()

class AudioStreamer:
    """
    Handles continuous audio capture with a rolling buffer.
    Configured for 16kHz mono 16-bit PCM, optimized for real-time VAD and STT.
    """

    def __init__(self, sample_rate: int = 16000, buffer_duration_s: int = 10) -> None:
        self.sample_rate = sample_rate
        self.buffer_duration_s = buffer_duration_s
        self.max_samples = sample_rate * buffer_duration_s
        self.channels = 1
        self.dtype = "int16"
        
        self._buffer: deque[np.ndarray] = deque()
        self._current_sample_count = 0
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None

    def _callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        """
        Callback for the sounddevice input stream.
        Runs in a separate high-priority thread.
        """
        if status:
            logger.warning("audio_stream_status_warning", status=str(status))
        
        with self._lock:
            # indata is a numpy array of shape (frames, channels)
            self._buffer.append(indata.copy())
            self._current_sample_count += frames
            
            # Maintain the rolling window (last 10 seconds)
            while self._current_sample_count > self.max_samples and self._buffer:
                removed = self._buffer.popleft()
                self._current_sample_count -= len(removed)

    def start(self) -> bool:
        """
        Starts the continuous audio input stream.
        Returns True if successful, False otherwise.
        """
        if self._stream is not None:
            logger.warning("audio_stream_already_running")
            return True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._callback,
                blocksize=int(self.sample_rate * 0.1)  # 100ms blocks
            )
            self._stream.start()
            logger.info(
                "audio_stream_started", 
                sample_rate=self.sample_rate, 
                buffer_duration_s=self.buffer_duration_s
            )
            return True
        except sd.PortAudioError as e:
            logger.error("audio_device_not_found", error=str(e))
            self._stream = None
            return False
        except Exception as e:
            logger.error("audio_stream_start_failed", error=str(e))
            self._stream = None
            return False

    def stop(self) -> None:
        """Stops and closes the audio input stream."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
                logger.info("audio_stream_stopped")
            except Exception as e:
                logger.error("audio_stream_stop_failed", error=str(e))
            finally:
                self._stream = None

    def get_buffer(self) -> np.ndarray:
        """
        Returns the entire current rolling buffer as a single numpy array.
        The array will have a maximum length corresponding to buffer_duration_s.
        """
        with self._lock:
            if not self._buffer:
                return np.array([], dtype=self.dtype)
            
            # Concatenate all chunks into a single 1D array
            return np.concatenate(self._buffer, axis=0).flatten()

    def clear_buffer(self) -> None:
        """Resets the rolling buffer."""
        with self._lock:
            self._buffer.clear()
            self._current_sample_count = 0
            logger.info("audio_buffer_cleared")

    @property
    def is_running(self) -> bool:
        """Returns True if the audio stream is currently active."""
        return self._stream is not None and self._stream.active
