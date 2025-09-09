

"""
Real-time AWS Transcribe (streaming) for voice agent.
- Captures mic audio (16 kHz mono PCM) and streams to Amazon Transcribe.
- Prints partial + final transcripts in real time.

Prereqs (Python 3.9+ recommended):
  pip install amazon-transcribe sounddevice boto3 numpy

AWS setup:
  - Ensure your AWS credentials are available via environment (AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY, optional AWS_SESSION_TOKEN) and AWS_DEFAULT_REGION.
  - Transcribe permissions: transcribe:StartStreamTranscriptionWebSocket or equivalent.

Run:
  python transcribe.py

Notes:
  - This is a minimal educational example. For production, consider WebRTC, VAD,
    barge-in handling, backpressure, error retries, and proper audio threading.
"""

import asyncio
import sys
from typing import Optional

import numpy as np
import sounddevice as sd

try:
    import pyaudio  # noqa: F401 (only used by sounddevice backend on some systems)
except Exception:
    pass

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler

# ---------- Config ----------
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
CHUNK_MS = 20  # size of mic frames to send to Transcribe
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)
LANGUAGE_CODE = "en-US"  # change as needed

# ---------- Audio Input (Mic) ----------

class MicStream:
    """Async microphone stream yielding raw int16 PCM frames."""

    def __init__(self, samplerate=SAMPLE_RATE, channels=CHANNELS, chunk_samples=CHUNK_SAMPLES):
        self.samplerate = samplerate
        self.channels = channels
        self.chunk_samples = chunk_samples
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._closed = asyncio.Event()

    def _callback(self, indata, frames, time_info, status):  # sounddevice callback
        if status:
            # Non-fatal warnings go to stderr.
            print(f"[mic] status: {status}", file=sys.stderr)
        # Ensure int16 bytes
        pcm = (indata.copy().astype(np.int16)).tobytes()
        # We may be called with variable frame counts; chop to fixed-size chunks
        # for smoother streaming.
        for start in range(0, len(pcm), self.chunk_samples * SAMPLE_WIDTH_BYTES * self.channels):
            chunk = pcm[start : start + self.chunk_samples * SAMPLE_WIDTH_BYTES * self.channels]
            if len(chunk) > 0:
                try:
                    self._queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    async def __aenter__(self):
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="int16",
            callback=self._callback,
            blocksize=self.chunk_samples,
        )
        self._stream.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._closed.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    async def generator(self):
        while not self._closed.is_set():
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                yield chunk
            except asyncio.TimeoutError:
                continue

# ---------- Transcribe Streaming ----------

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, stream, on_final_callback):
        super().__init__(stream)
        self.on_final_callback = on_final_callback

    async def handle_transcript_event(self, transcript_event):
        results = transcript_event.transcript.results
        for res in results:
            if len(res.alternatives) == 0:
                continue
            text = res.alternatives[0].transcript
            if res.is_partial:
                print(f"\r[partial] {text[:120]}", end="", flush=True)
            else:
                print("\r" + " " * 120, end="\r")  # clear partial line
                print(f"[final]   {text}")
                await self.on_final_callback(text)

async def stream_to_transcribe(audio_stream):
    client = TranscribeStreamingClient(region="us-west-2")  # specify actual region

    # Create bidirectional stream - pass parameters directly
    stream = await client.start_stream_transcription(
        language_code=LANGUAGE_CODE,
        media_sample_rate_hz=SAMPLE_RATE,
        media_encoding="pcm",
        enable_partial_results_stabilization=True,
        partial_results_stability="medium",
        enable_channel_identification=False,
        show_speaker_label=False,
    )

    async def mic_producer():
        async for chunk in audio_stream.generator():
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()

    async def handle_results():
        handler = MyEventHandler(stream.output_stream, on_final_callback=on_final_transcript)
        await handler.handle_events()

    async def on_final_transcript(text: str):
        # Process the final transcript (you can add your logic here)
        print(f"[processed] Final transcript: {text}")

    await asyncio.gather(mic_producer(), handle_results())

# ---------- Main ----------


# ...existing code...

async def stream_to_transcribe(audio_stream, on_partial=None, on_final=None):
    client = TranscribeStreamingClient(region="us-west-2")

    stream = await client.start_stream_transcription(
        language_code=LANGUAGE_CODE,
        media_sample_rate_hz=SAMPLE_RATE,
        media_encoding="pcm",
        enable_partial_results_stabilization=True,
        partial_results_stability="medium",
        enable_channel_identification=False,
        show_speaker_label=False,
    )

    async def mic_producer():
        async for chunk in audio_stream.generator():
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()

    class CustomEventHandler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, transcript_event):
            results = transcript_event.transcript.results
            for res in results:
                if len(res.alternatives) == 0:
                    continue
                text = res.alternatives[0].transcript
                if res.is_partial:
                    if on_partial:
                        await on_partial(text)
                else:
                    if on_final:
                        await on_final(text)

    async def handle_results():
        handler = CustomEventHandler(stream.output_stream)
        await handler.handle_events()

    await asyncio.gather(mic_producer(), handle_results())

# ...existing code...

async def main():
    print("Starting real-time Transcribe. Press Ctrl+C to stop.")
    try:
        async with MicStream() as mic:
            await stream_to_transcribe(mic)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    asyncio.run(main())
