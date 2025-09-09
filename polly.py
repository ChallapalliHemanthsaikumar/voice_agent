
from config import polly_client
import asyncio
import sounddevice as sd

import numpy as np
from typing import Optional
import threading
from queue import Queue
import time
from config import polly_client
import asyncio
import sounddevice as sd
import numpy as np
from typing import AsyncGenerator, Optional
import threading
from queue import Queue
import time
from config import polly_client
import asyncio
import sounddevice as sd
import numpy as np
from typing import AsyncGenerator
import time

# Even simpler version - play entire audio at once
async def synthesize_and_play_direct(text: str, voice_id: str = "Joanna"):
    """Convert text to speech and play directly without chunking."""
    try:
        print(f"Direct synthesis and playback: {text[:50]}...")
        
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='pcm',
            VoiceId=voice_id,
            SampleRate='16000'
        )
        
        audio_data = response['AudioStream'].read()
        print(f"Generated {len(audio_data)} bytes of audio")
        
        # Convert and play entire audio at once
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        print(f"Playing complete audio: {len(audio_array)} samples")
        
        sd.play(audio_array, samplerate=16000, blocking=True)
        print("Direct playback completed")
        
    except Exception as e:
        print(f"Error in direct playback: {e}")
        raise

async def main():
    print("=== Voice Agent Audio - Immediate Playback ===")
    
    # Step 1: Test audio system
  
    
    # Step 3: Test direct playback (no chunks)
    print("\n=== Testing Direct Playback ===")
    text2 = "This is direct playback without any chunking. The entire audio plays at once."
    
    try:
        await synthesize_and_play_direct(text2)
        print("✓ Direct playback completed")
    except Exception as e:
        print(f"❌ Direct playback failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())