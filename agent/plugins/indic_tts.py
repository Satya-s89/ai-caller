"""
agent/plugins/indic_tts.py
--------------------------
Streaming TTS plugin using Microsoft Edge TTS (te-IN-ShrutiNeural).

KEY UPGRADE — sentence-level streaming:
  Old path (batch):  Wait for full LLM response → synthesize → play
  New path (stream): LLM token arrives → detect sentence end → synthesize
                     immediately → start playing while LLM generates next sentence

This cuts perceived latency by ~0.5-1 s because the user hears the first
sentence before the LLM has even finished the response.
"""

from __future__ import annotations

import io
import logging
import os

import edge_tts
import numpy as np
import soundfile as sf
from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

logger = logging.getLogger("agent.indic_tts")

EDGE_TTS_VOICE  = os.getenv("TTS_VOICE", "te-IN-ShrutiNeural")
NATIVE_SR       = 24_000          # Edge TTS native sample rate

# Characters that mark the end of a speakable unit
SENTENCE_ENDS = frozenset('.?!।|')
# Maximum characters to accumulate before forcing a flush (avoids long silences
# when the LLM produces punctuation-free text)
MAX_BUFFER_CHARS = 120


# ── helpers ───────────────────────────────────────────────────────────────────

async def _tts_to_pcm(text: str) -> tuple[bytes, int]:
    """Call Edge TTS → return (int16 PCM bytes, sample_rate)."""
    communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
    mp3_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]

    if not mp3_data:
        return b"", NATIVE_SR

    data, sr = sf.read(io.BytesIO(mp3_data))
    if data.ndim > 1:
        data = data[:, 0]                          # stereo → mono
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("int16").tobytes()
    return pcm, int(sr)


def _push_pcm(pcm: bytes, sr: int, output_emitter: tts.AudioEmitter) -> None:
    """Push PCM bytes to the audio emitter in 100 ms chunks, then flush."""
    chunk_size = int(sr * 2 * 0.1)   # 100 ms of 16-bit mono PCM
    for offset in range(0, len(pcm), chunk_size):
        chunk = pcm[offset : offset + chunk_size]
        if chunk:
            output_emitter.push(chunk)
    output_emitter.flush()


# ── streaming stream ──────────────────────────────────────────────────────────

class IndicTTSSynthesizeStream(tts.SynthesizeStream):
    """
    Sentence-level streaming TTS stream.

    Tokens arrive one-by-one from the LLM.  The moment a sentence boundary
    is detected (or MAX_BUFFER_CHARS is reached), the buffered sentence is
    sent to Edge TTS.  Audio for that sentence starts playing while the LLM
    is still generating the remainder of the response.
    """

    def __init__(self, tts_instance: "IndicTTS", opts: APIConnectOptions) -> None:
        super().__init__(tts=tts_instance, conn_options=opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        buffer       = ""
        initialized  = False
        cached_sr    = NATIVE_SR

        async def _flush_buffer(text: str) -> None:
            nonlocal initialized, cached_sr
            text = text.strip()
            if not text:
                return

            pcm, sr = await _tts_to_pcm(text)
            if not pcm:
                return

            cached_sr = sr
            if not initialized:
                output_emitter.initialize(
                    request_id="edge_tts",
                    sample_rate=sr,
                    num_channels=1,
                    mime_type="audio/pcm",
                )
                initialized = True

            _push_pcm(pcm, sr, output_emitter)
            logger.info("TTS streamed %d bytes: %s", len(pcm), text[:50])

        try:
            async for item in self._input_ch:
                if isinstance(item, tts.SynthesizeStream._FlushSentinel):
                    # Explicit flush from the framework
                    if buffer.strip():
                        await _flush_buffer(buffer)
                        buffer = ""
                else:
                    buffer += item
                    stripped = buffer.rstrip()
                    # Flush on sentence boundary or max-buffer overflow
                    if stripped and (
                        (stripped[-1] in SENTENCE_ENDS and len(stripped) > 4)
                        or len(stripped) >= MAX_BUFFER_CHARS
                    ):
                        await _flush_buffer(buffer)
                        buffer = ""

            # Drain any trailing text
            if buffer.strip():
                await _flush_buffer(buffer)

            # If nothing was pushed (e.g. empty/whitespace response)
            if not initialized:
                output_emitter.initialize(
                    request_id="edge_tts",
                    sample_rate=NATIVE_SR,
                    num_channels=1,
                    mime_type="audio/pcm",
                )

        except Exception:
            logger.exception("Edge-TTS streaming synthesis failed")
            raise


# ── batch stream (fallback) ───────────────────────────────────────────────────

class IndicTTSChunkedStream(tts.ChunkedStream):
    """Batch synthesis (used when the agent calls synthesize() explicitly)."""

    def __init__(self, tts_instance: "IndicTTS", text: str, opts: APIConnectOptions) -> None:
        super().__init__(tts=tts_instance, input_text=text, conn_options=opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        pcm, sr = await _tts_to_pcm(self._input_text)
        if not pcm:
            raise RuntimeError(f"Edge-TTS returned no audio for: {self._input_text[:60]!r}")

        logger.info("TTS batch %d bytes @ %d Hz: %r", len(pcm), sr, self._input_text[:50])
        output_emitter.initialize(
            request_id="edge_tts",
            sample_rate=sr,
            num_channels=1,
            mime_type="audio/pcm",
        )
        _push_pcm(pcm, sr, output_emitter)


# ── main TTS class ────────────────────────────────────────────────────────────

class IndicTTS(tts.TTS):
    """
    Telugu TTS plugin — Edge TTS with sentence-level streaming.

    streaming=True  →  agent uses stream() for low-latency sentence-by-sentence
                       synthesis while LLM generates the rest of the response.
    """

    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=NATIVE_SR,
            num_channels=1,
        )

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> IndicTTSChunkedStream:
        return IndicTTSChunkedStream(self, text, conn_options)

    def stream(
        self,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> IndicTTSSynthesizeStream:
        return IndicTTSSynthesizeStream(self, conn_options)
