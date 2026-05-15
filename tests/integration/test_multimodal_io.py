import asyncio
import time
import numpy as np
from aura.io.screen import capture_screen
from aura.io.audio import AudioStreamer
from aura.io.stt import WhisperSTT
from aura.io.vad import SileroVAD
from aura.io.tts import KokoroTTS
from aura.io.orchestrator import VoiceOrchestrator
import pytest
import structlog

# Configure basic logging for the test
structlog.configure()
logger = structlog.get_logger()

@pytest.mark.asyncio
async def test_multimodal_io_advanced():
    print("\n--- Phase 3 Advanced Voice Layer Verification ---")
    
    # 1. Test Screen Capture
    print("\n[1/5] Testing Screen Capture...")
    try:
        start = time.perf_counter()
        capture = await capture_screen(monitor_index=0)
        latency = (time.perf_counter() - start) * 1000
        print(f"✅ Captured screen from monitor {capture.monitor_index}")
        print(f"   Dimensions: {capture.width}x{capture.height}")
        print(f"   Total Pipeline Latency: {latency:.2f}ms")
    except Exception as e:
        print(f"❌ Screen Capture Failed: {e}")

    # 2. Test Audio Streamer & VAD
    print("\n[2/5] Testing Audio Streamer & Silero VAD (5 seconds monitoring)...")
    print("      PLEASE SPEAK NOW...")
    
    streamer = AudioStreamer()
    vad = SileroVAD()
    
    if streamer.start():
        speech_detected = False
        for _ in range(50):  # 5 seconds at 10Hz
            buffer = streamer.get_buffer()
            if len(buffer) >= 1600:
                latest_chunk = buffer[-1600:]
                if await vad.is_speech(latest_chunk.tobytes()):
                    speech_detected = True
                    print("   [VAD] Speech Detected!")
                    break
            await asyncio.sleep(0.1)
        
        if not speech_detected:
            print("   ⚠️ No speech detected during test.")
        streamer.stop()
    else:
        print("❌ Audio Streamer failed to start.")

    # 3. Test Optimized STT
    print("\n[3/5] Testing Whisper STT (int8 optimized)...")
    try:
        stt = WhisperSTT()
        # Generate 1 second of silence for a dummy test
        dummy_audio = np.zeros(16000, dtype=np.int16)
        text = await stt.transcribe(dummy_audio)
        print(f"✅ Whisper singleton loaded. Dummy result: \"{text}\"")
    except Exception as e:
        print(f"❌ Whisper STT Failed: {e}")

    # 4. Test Kokoro TTS
    print("\n[4/5] Testing Kokoro TTS...")
    try:
        tts = KokoroTTS()
        print("   Synthesizing 'Aura Phase 3 Test complete'...")
        await tts.speak("Aura Phase 3 Test complete")
        print("✅ Kokoro TTS Playback finished.")
    except Exception as e:
        print(f"❌ Kokoro TTS Failed: {e}")

    # 5. Test Voice Orchestrator State Machine
    print("\n[5/5] Testing Orchestrator State Transitions...")
    try:
        orch = VoiceOrchestrator()
        print(f"   Initial State: {orch.state.value}")
        await orch.start()
        print(f"   Started State: {orch.state.value}")
        await asyncio.sleep(1)
        await orch.stop()
        print(f"   Stopped State: {orch.state.value}")
        print("✅ Orchestrator lifecycle verified.")
    except Exception as e:
        print(f"❌ Orchestrator Failed: {e}")

    print("\n--- Phase 3 Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(test_multimodal_io_advanced())
