from __future__ import annotations

import asyncio
import base64
import io
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mss
import structlog
from PIL import Image

if TYPE_CHECKING:
    from typing import Final

logger = structlog.get_logger()

# Constants for the capture pipeline
MAX_SIDE: Final[int] = 1024
JPEG_QUALITY: Final[int] = 85

@dataclass
class ScreenCapture:
    """
    Container for a processed screen capture ready for LLM consumption.
    
    Fields:
        base64_jpeg: The base64-encoded JPEG string.
        width: Width of the processed image in pixels.
        height: Height of the processed image in pixels.
        monitor_index: The index of the monitor that was captured.
        timestamp: Unix timestamp of the capture.
    """
    base64_jpeg: str
    width: int
    height: int
    monitor_index: int
    timestamp: float

def _capture_and_process(monitor_index: int) -> ScreenCapture:
    """
    Synchronous implementation of the screen capture pipeline.
    Executed in a thread pool to avoid blocking the event loop.
    """
    start_time = time.perf_counter()
    
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            
            # monitor_index 0 in Aura refers to the primary monitor (mss.monitors[1]).
            # mss.monitors[0] is the virtual screen covering all monitors.
            target_index = monitor_index
            if target_index == 0:
                target_index = 1
                
            if target_index < 0 or target_index >= len(monitors):
                logger.warning(
                    "invalid_monitor_index", 
                    provided=monitor_index, 
                    available_count=len(monitors) - 1,
                    falling_back_to=1
                )
                target_index = 1

            monitor = monitors[target_index]
            sct_img = sct.grab(monitor)
            
            # Convert mss pixels to PIL Image
            # 'BGRX' is the raw format returned by mss on most platforms
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            orig_w, orig_h = img.size
            
            # Resize while preserving aspect ratio (1024px longest side)
            if orig_w > MAX_SIDE or orig_h > MAX_SIDE:
                ratio = MAX_SIDE / max(orig_w, orig_h)
                new_size = (int(orig_w * ratio), int(orig_h * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            processed_w, processed_h = img.size

            # Compress to JPEG at 85% quality
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
            base64_jpeg = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "screen_capture_completed",
                monitor_index=target_index,
                original_size=f"{orig_w}x{orig_h}",
                final_size=f"{processed_w}x{processed_h}",
                latency_ms=round(latency_ms, 2)
            )
            
            return ScreenCapture(
                base64_jpeg=base64_jpeg,
                width=processed_w,
                height=processed_h,
                monitor_index=target_index,
                timestamp=time.time()
            )
    except Exception as e:
        logger.error("screen_capture_failed", error=str(e), monitor_index=monitor_index)
        raise

async def capture_screen(monitor_index: int = 0) -> ScreenCapture:
    """
    Captures the screen, resizes it, and returns a base64 encoded JPEG.
    
    Args:
        monitor_index: The index of the monitor to capture. 0 is the primary monitor.
        
    Returns:
        A ScreenCapture object containing the processed image and metadata.
    """
    return await asyncio.to_thread(_capture_and_process, monitor_index)
