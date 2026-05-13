import asyncio
import base64
import io
import time
from dataclasses import dataclass
from typing import Optional

import mss
import structlog
from PIL import Image

logger = structlog.get_logger()

@dataclass
class ScreenCapture:
    """
    Container for a processed screen capture ready for LLM consumption.
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
    
    with mss.mss() as sct:
        # mss monitor indices: 0 is all monitors combined, 1 is the first monitor
        # We adjust to 1-based if the user provides 0 as 'first monitor'
        # or follow mss convention if specified. 
        # docs/Multimodal_IO.md likely specifies this. 
        # mss.monitors[0] is the bounding box of all monitors.
        # We'll treat monitor_index=0 as the primary monitor (mss.monitors[1])
        # unless monitor_index matches an index in mss.monitors.
        
        monitors = sct.monitors
        if monitor_index < 0 or monitor_index >= len(monitors):
            logger.warning("invalid_monitor_index", provided=monitor_index, count=len(monitors))
            monitor_index = 1 # Fallback to primary
        elif monitor_index == 0 and len(monitors) > 1:
            # If user asks for 0, they might mean 'all' or 'primary'.
            # Usually in Aura, 0 is the primary monitor.
            monitor_index = 1

        monitor = monitors[monitor_index]
        sct_img = sct.grab(monitor)
        
        # Convert to PIL Image
        # mss 'bgra' is the fastest format to grab
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        original_width, original_height = img.size
        
        # Resize: 1024px longest side preserving aspect ratio
        max_size = 1024
        if original_width > max_size or original_height > max_size:
            if original_width > original_height:
                new_width = max_size
                new_height = int(original_height * (max_size / original_width))
            else:
                new_height = max_size
                new_width = int(original_width * (max_size / original_height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            new_width, new_height = original_width, original_height

        # Encode to JPEG at 85% quality
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        base64_jpeg = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "screen_captured",
            monitor_index=monitor_index,
            width=new_width,
            height=new_height,
            latency_ms=round(latency_ms, 2)
        )
        
        return ScreenCapture(
            base64_jpeg=base64_jpeg,
            width=new_width,
            height=new_height,
            monitor_index=monitor_index,
            timestamp=time.time()
        )

async def capture_screen(monitor_index: int = 0) -> ScreenCapture:
    """
    Captures the screen, resizes it, and returns a base64 encoded JPEG.
    Runs the CPU-bound capture and processing in a separate thread.
    """
    return await asyncio.to_thread(_capture_and_process, monitor_index)
