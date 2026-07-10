"""
agent/plugins/indic_tts.py
---------------------------
LiveKit Agents 1.6.5 custom TTS plugin.

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
import uuid
import wave

import httpx
from dotenv import load_dotenv
from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

load_dotenv()
logger = logging.getLogger("agent.indic_tts")

TTS_SERVICE_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8002")
SAMPLE_RATE = int(os.getenv("CALL_SAMPLE_RATE", "8000"))


def _parse_wav(wav_bytes: bytes) -> tuple[bytes, int, int]:
    """Return (raw_pcm_bytes, sample_rate, num_channels) from a WAV blob."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        sr = wf.getframerate()
        nc = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    return raw, sr, nc


class IndicTTSStream(tts.ChunkedStream):
    """Streams synthesized audio frames from the local TTS service."""

    def __init__(self, tts_instance: "IndicTTS", text: str, opts: APIConnectOptions):
        super().__init__(tts=tts_instance, input_text=text, conn_options=opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{TTS_SERVICE_URL}/synthesize",
                    json={"text": self._input_text, "sample_rate": SAMPLE_RATE},
                )
            resp.raise_for_status()

            raw_pcm, sr, nc = _parse_wav(resp.content)

            output_emitter.initialize(
                request_id=str(uuid.uuid4()),
                sample_rate=sr,
                num_channels=nc,
                mime_type="audio/pcm",
            )
            output_emitter.push(raw_pcm)

        except Exception:
            logger.exception("TTS service call failed")
            # Safely initialize the emitter to prevent the job runner from crashing with "AudioEmitter isn't started"
            output_emitter.initialize(
                request_id=str(uuid.uuid4()),
                sample_rate=SAMPLE_RATE,
                num_channels=1,
                mime_type="audio/pcm",
            )


class IndicTTS(tts.TTS):
    """Custom TTS plugin backed by the local IndicF5 service."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
        )

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> IndicTTSStream:
        return IndicTTSStream(self, text, conn_options)
