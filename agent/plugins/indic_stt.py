"""
agent/plugins/indic_stt.py
---------------------------
LiveKit Agents 1.6.5 custom STT plugin.

Proxies audio frames to the local IndicConformer STT service
(stt_service/main.py running on STT_SERVICE_URL).

Usage in AgentSession:
    from agent.plugins.indic_stt import IndicSTT
    session = AgentSession(stt=IndicSTT(), ...)
"""

from __future__ import annotations

import io
import logging
import os
import wave

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import stt
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)

load_dotenv()
logger = logging.getLogger("agent.indic_stt")

STT_SERVICE_URL = os.getenv("STT_SERVICE_URL", "http://127.0.0.1:8001")
SAMPLE_RATE = 16_000   # IndicConformer expects 16kHz
CHANNELS = 1


def _frames_to_wav(frames: list) -> bytes:
    """Concatenate AudioFrame objects into a single WAV byte blob, resampling if necessary."""
    if not frames:
        return b""
        
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        
        # Check first frame sample rate
        src_sr = frames[0].sample_rate
        resampler = None
        if src_sr != SAMPLE_RATE:
            logger.info("STT input audio has sample rate %d Hz, resampling to %d Hz", src_sr, SAMPLE_RATE)
            resampler = rtc.AudioResampler(
                src_sr,
                SAMPLE_RATE,
                quality=rtc.AudioResamplerQuality.HIGH,
            )
            
        for frame in frames:
            if resampler:
                resampled_frames = resampler.push(frame)
                for rf in resampled_frames:
                    wf.writeframes(bytes(rf.data))
            else:
                wf.writeframes(bytes(frame.data))
                
        if resampler:
            for rf in resampler.flush():
                wf.writeframes(bytes(rf.data))
                
    return buf.getvalue()


async def _post_wav(wav_bytes: bytes) -> str:
    """Send WAV bytes to the STT service and return the transcript text."""
    if not wav_bytes:
        return ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{STT_SERVICE_URL}/transcribe",
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        )
    resp.raise_for_status()
    return resp.json().get("text", "")


class IndicSTTStream(stt.RecognizeStream):
    """Accumulates audio frames, then sends to the STT service on flush/end-of-speech."""

    def __init__(self, stt_instance: "IndicSTT", opts: APIConnectOptions):
        super().__init__(stt=stt_instance, conn_options=opts, sample_rate=SAMPLE_RATE)
        self._frames: list[rtc.AudioFrame] = []

    async def _run(self) -> None:
        """Consume frames pushed by the framework; yield SpeechEvents."""
        logger.info("IndicSTTStream input channel listener started")
        async for event in self._input_ch:
            # _FlushSentinel marks end-of-utterance
            if isinstance(event, self._FlushSentinel):
                logger.info("IndicSTTStream received _FlushSentinel (end of speech VAD event)")
                if self._frames:
                    await self._transcribe_and_emit()
                    self._frames.clear()
                else:
                    logger.info("IndicSTTStream: no frames to transcribe on flush")
            elif isinstance(event, rtc.AudioFrame):
                self._frames.append(event)
                if len(self._frames) % 50 == 0:
                    logger.info("IndicSTTStream: accumulated %d audio frames", len(self._frames))

    async def _transcribe_and_emit(self) -> None:
        wav_bytes = _frames_to_wav(self._frames)
        logger.info("STT: transcribing %d frames (%d bytes WAV)", len(self._frames), len(wav_bytes))
        try:
            text = await _post_wav(wav_bytes)
            logger.info("STT result: %r", text)
            if text:
                self._event_ch.send_nowait(
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[stt.SpeechData(text=text, language="te")],
                    )
                )
            else:
                logger.warning("STT returned empty text — no event emitted")
        except Exception:
            logger.exception("STT service call failed")


class IndicSTT(stt.STT):
    """Custom STT plugin backed by the local IndicConformer service.
    Set streaming=False so that the framework wraps it with stt.StreamAdapter using VAD.
    """

    def __init__(self) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False),
        )

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> IndicSTTStream:
        return IndicSTTStream(self, conn_options)

    async def _recognize_impl(
        self,
        buffer: "stt.AudioBuffer",
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        """Batch-recognize a complete audio buffer (non-streaming path)."""
        # Normalise: single frame or iterable
        if hasattr(buffer, "data") and hasattr(buffer, "sample_rate"):
            frames: list = [buffer]
        else:
            frames = list(buffer)  # type: ignore[arg-type]

        wav_bytes = _frames_to_wav(frames)
        try:
            text = await _post_wav(wav_bytes)
            logger.info("STT batch result: %r", text)
        except Exception:
            logger.exception("STT batch service call failed")
            text = ""

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language="te")],
        )
