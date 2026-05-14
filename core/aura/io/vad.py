import asyncio
import time
from typing import Optional

import numpy as np
import onnxruntime as ort
import structlog

logger = structlog.get_logger()

class SileroVAD:
    """
    Voice Activity Detection using Silero VAD (ONNX).
    Lazily loads the model and performs inference in a separate thread.
    """
    _instance: Optional['SileroVAD'] = None
    _session: Optional[ort.InferenceSession] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SileroVAD, cls).__new__(cls)
        return cls._instance

    async def _get_session(self) -> ort.InferenceSession:
        """
        Lazily initializes the ONNX runtime session for Silero VAD.
        Downloads the model if necessary (handled by silero-vad package logic).
        """
        if self._session is not None:
            return self._session

        async with self._lock:
            if self._session is not None:
                return self._session

            import silero_vad

            logger.info("loading_silero_vad_model")
            start_time = time.perf_counter()
            
            try:
                # Get the model path from the silero-vad package
                model_path = silero_vad.get_model_path()
                
                # Configure ONNX Runtime for CPU usage
                opts = ort.SessionOptions()
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                opts.inter_op_num_threads = 1
                opts.intra_op_num_threads = 1
                
                self._session = ort.InferenceSession(
                    model_path, 
                    sess_options=opts, 
                    providers=['CPUExecutionProvider']
                )
                
                latency = time.perf_counter() - start_time
                logger.info("silero_vad_model_loaded", latency_s=round(latency, 2))
            except Exception as e:
                logger.error("silero_vad_load_failed", error=str(e))
                raise

            return self._session

    def _process_inference(self, session: ort.InferenceSession, audio_float32: np.ndarray) -> bool:
        """
        Performs the synchronous ONNX inference.
        """
        # Silero VAD expects [1, samples] input
        if audio_float32.ndim == 1:
            audio_float32 = np.expand_dims(audio_float32, axis=0)
            
        # Prepare inputs for the Silero VAD ONNX model
        # sr: Sample Rate (must be 8000 or 16000)
        # h, c: Hidden states for the RNN
        sr = np.array([16000], dtype=np.int64)
        h = np.zeros((2, 1, 64), dtype=np.float32)
        c = np.zeros((2, 1, 64), dtype=np.float32)
        
        inputs = {
            'input': audio_float32,
            'sr': sr,
            'h': h,
            'c': c
        }
        
        # Run inference
        out, _, _ = session.run(None, inputs)
        
        # Output 'out' is the probability [1, 1]
        probability = out[0][0]
        return bool(probability >= 0.5)

    async def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Detects if the provided audio chunk contains speech.
        Expects 16kHz mono 16-bit PCM bytes.
        """
        if not audio_chunk:
            return False

        try:
            session = await self._get_session()
            
            # Convert bytes to float32 numpy array
            # 16-bit PCM is -32768 to 32767, normalize to -1.0 to 1.0
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            start_time = time.perf_counter()
            # Run inference in a thread pool to avoid blocking the event loop
            is_voice = await asyncio.to_thread(self._process_inference, session, audio_float32)
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            if is_voice:
                logger.debug("speech_detected", confidence_threshold=0.5, latency_ms=round(latency_ms, 2))
                
            return is_voice
        except Exception as e:
            logger.error("vad_inference_failed", error=str(e))
            return False
