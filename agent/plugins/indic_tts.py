"""
agent/plugins/indic_tts.py
--------------------------
Streaming TTS plugin — Sarvam AI bulbul:v2 (primary) with Edge TTS fallback.

Provider selection:
  - SARVAM_API_KEY set → Sarvam bulbul:v2  (natural Indian Telugu voice)
  - SARVAM_API_KEY not set → Edge TTS te-IN-ShrutiNeural (Microsoft, free)

KEY FEATURE — sentence-level streaming:
  LLM token arrives → detect sentence end → synthesize immediately →
  start playing while LLM generates next sentence.
  Cuts perceived latency by ~0.5-1 s.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import subprocess

import aiohttp
import edge_tts
import numpy as np
import soundfile as sf
from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

logger = logging.getLogger("agent.indic_tts")

EDGE_TTS_VOICE      = os.getenv("TTS_VOICE", "te-IN-ShrutiNeural")
SARVAM_TTS_SPEAKER  = os.getenv("SARVAM_TTS_SPEAKER", "meera")   # meera | pavithra
SARVAM_API_URL      = "https://api.sarvam.ai/text-to-speech"
NATIVE_SR           = 22_050   # Sarvam native; Edge TTS is 24 kHz (detected at runtime)

# Sentence boundary characters
SENTENCE_ENDS    = frozenset('.?!।|')
MAX_BUFFER_CHARS = 120   # flush before this many chars even without punctuation


# ── TTS provider helpers ───────────────────────────────────────────────────────

async def _sarvam_tts_to_pcm(text: str) -> tuple[bytes, int]:
    """Call Sarvam bulbul:v2 → (int16 PCM bytes, sample_rate)."""
    api_key = os.getenv("SARVAM_API_KEY", "")
    payload = {
        "inputs": [text],
        "target_language_code": "te-IN",
        "speaker": SARVAM_TTS_SPEAKER,
        "model": "bulbul:v2",
        "enable_preprocessing": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SARVAM_API_URL,
                json=payload,
                headers={"api-subscription-key": api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Sarvam TTS error %d: %s", resp.status, body[:200])
                    return b"", NATIVE_SR
                data = await resp.json()
                audios = data.get("audios", [])
                if not audios:
                    logger.error("Sarvam TTS: no 'audios' in response: %s", str(data)[:200])
                    return b"", NATIVE_SR
                audio_b64 = audios[0]

        wav_bytes = base64.b64decode(audio_b64)
        arr, sr = sf.read(io.BytesIO(wav_bytes))  # Sarvam returns WAV
        if arr.ndim > 1:
            arr = arr[:, 0]
        pcm = (np.clip(arr, -1.0, 1.0) * 32767).astype("int16").tobytes()
        return pcm, int(sr)

    except Exception:
        logger.exception("Sarvam TTS failed, falling back to Edge TTS")
        return b"", NATIVE_SR


async def _edge_tts_to_pcm(text: str) -> tuple[bytes, int]:
    """Call Edge TTS → (int16 PCM bytes, sample_rate).

    Edge TTS streams MP3 audio. soundfile cannot read MP3 without special
    libsndfile build, so we decode via ffmpeg subprocess when available.
    """
    communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
    mp3_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]

    if not mp3_data:
        return b"", 24_000

    # Try soundfile first (works if libsndfile was built with MP3/sndio support)
    try:
        arr, sr = sf.read(io.BytesIO(mp3_data))
        if arr.ndim > 1:
            arr = arr[:, 0]
        pcm = (np.clip(arr, -1.0, 1.0) * 32767).astype("int16").tobytes()
        return pcm, int(sr)
    except Exception:
        pass  # fall through to ffmpeg

    # Fallback: decode MP3 → raw s16le PCM via ffmpeg (no extra Python deps)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", "pipe:0",
                "-f", "s16le", "-ar", "24000", "-ac", "1",
                "pipe:1", "-loglevel", "quiet",
            ],
            input=mp3_data,
            capture_output=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout:
            logger.debug("Edge TTS: decoded MP3 via ffmpeg (%d bytes)", len(result.stdout))
            return result.stdout, 24_000
        logger.error("Edge TTS ffmpeg decode failed: %s", result.stderr[:200])
    except FileNotFoundError:
        logger.error("Edge TTS: ffmpeg not found — install ffmpeg to use Edge TTS fallback")
    except Exception:
        logger.exception("Edge TTS: ffmpeg fallback failed")

    return b"", 24_000


async def _tts_to_pcm(text: str) -> tuple[bytes, int]:
    """Route to Sarvam TTS if key available, else Edge TTS."""
    if os.getenv("SARVAM_API_KEY"):
        pcm, sr = await _sarvam_tts_to_pcm(text)
        if pcm:
            return pcm, sr
        # fall through to Edge TTS on Sarvam failure
        logger.warning("Sarvam TTS returned empty, using Edge TTS fallback")
    return await _edge_tts_to_pcm(text)


def _push_pcm(pcm: bytes, sr: int, output_emitter: tts.AudioEmitter) -> None:
    """Push PCM bytes to audio emitter in 100 ms chunks, then flush."""
    chunk_size = int(sr * 2 * 0.1)  # 100 ms of 16-bit mono
    for offset in range(0, len(pcm), chunk_size):
        chunk = pcm[offset : offset + chunk_size]
        if chunk:
            output_emitter.push(chunk)
    output_emitter.flush()


# ── streaming synthesis stream ─────────────────────────────────────────────────

class IndicTTSSynthesizeStream(tts.SynthesizeStream):
    """
    Sentence-level streaming TTS.
    Flushes to TTS as soon as a sentence boundary is detected so audio
    starts playing before the LLM finishes the full response.
    """

    def __init__(self, tts_instance: "IndicTTS", opts: APIConnectOptions) -> None:
        super().__init__(tts=tts_instance, conn_options=opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        buffer      = ""
        initialized = False
        cached_sr   = NATIVE_SR

        async def _flush(text: str) -> None:
            nonlocal initialized, cached_sr
            text = text.strip()
            if not text:
                return

            pcm, sr = await _tts_to_pcm(text)
            if not pcm:
                return

            cached_sr = sr
            if not initialized:
                provider = "Sarvam" if os.getenv("SARVAM_API_KEY") else "Edge"
                output_emitter.initialize(
                    request_id=f"{provider.lower()}_tts",
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
                    if buffer.strip():
                        await _flush(buffer)
                        buffer = ""
                else:
                    buffer += item
                    stripped = buffer.rstrip()
                    if stripped and (
                        (stripped[-1] in SENTENCE_ENDS and len(stripped) > 4)
                        or len(stripped) >= MAX_BUFFER_CHARS
                    ):
                        await _flush(buffer)
                        buffer = ""

            if buffer.strip():
                await _flush(buffer)

            if not initialized:
                output_emitter.initialize(
                    request_id="tts",
                    sample_rate=NATIVE_SR,
                    num_channels=1,
                    mime_type="audio/pcm",
                )

        except Exception:
            logger.exception("TTS streaming synthesis failed")
            raise


# ── batch synthesis (fallback) ─────────────────────────────────────────────────

class IndicTTSChunkedStream(tts.ChunkedStream):
    """Batch synthesis used when the agent calls synthesize() explicitly."""

    def __init__(self, tts_instance: "IndicTTS", text: str, opts: APIConnectOptions) -> None:
        super().__init__(tts=tts_instance, input_text=text, conn_options=opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        pcm, sr = await _tts_to_pcm(self._input_text)
        if not pcm:
            raise RuntimeError(f"TTS returned no audio for: {self._input_text[:60]!r}")

        provider = "Sarvam" if os.getenv("SARVAM_API_KEY") else "Edge"
        logger.info("TTS batch %d bytes @ %d Hz (%s): %s",
                    len(pcm), sr, provider, self._input_text[:50])
        output_emitter.initialize(
            request_id=f"{provider.lower()}_tts",
            sample_rate=sr,
            num_channels=1,
            mime_type="audio/pcm",
        )
        _push_pcm(pcm, sr, output_emitter)


# ── main TTS class ─────────────────────────────────────────────────────────────

class IndicTTS(tts.TTS):
    """
    Telugu TTS — Sarvam bulbul:v2 (primary) or Edge TTS (fallback).
    streaming=True enables sentence-level synthesis for low latency.
    """

    def __init__(self) -> None:
        provider = "Sarvam bulbul:v2" if os.getenv("SARVAM_API_KEY") else "Edge TTS"
        logger.info("TTS provider: %s", provider)
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
