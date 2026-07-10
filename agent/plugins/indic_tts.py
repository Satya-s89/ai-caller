"""
agent/plugins/indic_tts.py
---------------------------
LiveKit Agents custom TTS plugin.

Proxies synthesis requests to the local IndicF5 TTS service
(tts_service/main.py running on TTS_SERVICE_URL).

Usage in AgentSession:
    from agent.plugins.indic_tts import IndicTTS
    session = AgentSession(tts=IndicTTS(), ...)
"""

from __future__ import annotations

import io
import logging
import os
import wave
from typing import AsyncIterator

import httpx
import numpy as np
from dotenv import load_dotenv
from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

load_dotenv()
logger = logging.getLogger("agent.indic_tts")

TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8002")
SAMPLE_RATE = int(os.getenv("CALL_SAMPLE_RATE", "8000"))
FRAME_DURATION_MS = 20     # chunk size sent to LiveKit room audio track


def _wav_to_frames(wav_bytes: bytes) -> list[tts.SynthesizedAudio]:
    """Split a WAV byte blob into fixed-duration AudioFrame chunks."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())

    samples = np.frombuffer(raw, dtype=np.int16)
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

    frame_samples = int(sr * FRAME_DURATION_MS / 1000)
    frames: list[tts.SynthesizedAudio] = []
    for start in range(0, len(samples), frame_samples):
        chunk = samples[start : start + frame_samples]
        # Pad final chunk if needed
        if len(chunk) < frame_samples:
            chunk = np.pad(chunk, (0, frame_samples - len(chunk)))
        audio_frame = tts.AudioFrame(
            data=chunk,
            sample_rate=sr,
            num_channels=1,
            samples_per_channel=frame_samples,
        )
        frames.append(tts.SynthesizedAudio(frame=audio_frame, request_id=""))
    return frames


class IndicTTSStream(tts.ChunkedStream):
    """Streams synthesized audio frames from the local TTS service."""

    def __init__(self, tts_instance: "IndicTTS", text: str, opts: APIConnectOptions):
        super().__init__(tts_instance, text, opts)
        self._text = text

    async def _run(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{TTS_SERVICE_URL}/synthesize",
                    json={"text": self._text, "sample_rate": SAMPLE_RATE},
                )
            resp.raise_for_status()
            frames = _wav_to_frames(resp.content)
            for frame in frames:
                self._event_ch.send_nowait(frame)
        except Exception:
            logger.exception("TTS service call failed")


class IndicTTS(tts.TTS):
    """Custom TTS plugin backed by the local IndicF5 service."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )

    def synthesize(self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> IndicTTSStream:
        return IndicTTSStream(self, text, conn_options)
