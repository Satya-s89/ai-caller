"""
agent/plugins/indic_stt.py
---------------------------
LiveKit Agents custom STT plugin.

Proxies audio frames to the local IndicConformer STT service
(stt_service/main.py running on STT_SERVICE_URL).

Usage in AgentSession:
    from agent.plugins.indic_stt import IndicSTT
    session = AgentSession(stt=IndicSTT(), ...)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import wave
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv
from livekit.agents import stt
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

load_dotenv()
logger = logging.getLogger("agent.indic_stt")

STT_SERVICE_URL = os.getenv("STT_SERVICE_URL", "http://localhost:8001")
SAMPLE_RATE = 16_000   # frames are collected at this rate before POSTing
CHANNELS = 1


def _frames_to_wav(frames: list[stt.AudioFrame]) -> bytes:
    """Concatenate AudioFrame objects into a single WAV byte blob."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        for frame in frames:
            wf.writeframes(frame.data.tobytes())
    return buf.getvalue()


class IndicSTTStream(stt.SpeechStream):
    """Accumulates audio frames, then sends to the STT service on end-of-speech."""

    def __init__(self, stt_instance: "IndicSTT", opts: APIConnectOptions):
        super().__init__(stt_instance, opts)
        self._frames: list[stt.AudioFrame] = []

    async def _run(self) -> None:
        """Consume frames pushed by the framework; yield SpeechEvents."""
        async for event in self._input_ch:
            if isinstance(event, self.InputEndedEvent):
                if self._frames:
                    await self._transcribe_and_emit()
                    self._frames.clear()
            elif isinstance(event, stt.AudioFrame):
                self._frames.append(event)

    async def _transcribe_and_emit(self) -> None:
        wav_bytes = _frames_to_wav(self._frames)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{STT_SERVICE_URL}/transcribe",
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("text", "")
            if text:
                logger.debug("STT result: %s", text)
                self._event_ch.send_nowait(
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[stt.SpeechData(text=text, language="te")],
                    )
                )
        except Exception:
            logger.exception("STT service call failed")


class IndicSTT(stt.STT):
    """Custom STT plugin backed by the local IndicConformer service."""

    def __init__(self) -> None:
        super().__init__(streaming_supported=True, capabilities=stt.STTCapabilities(streaming=True, interim_results=False))

    def stream(self, *, language: str | None = "te", conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> IndicSTTStream:
        return IndicSTTStream(self, conn_options)
