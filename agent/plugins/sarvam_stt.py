"""
agent/plugins/sarvam_stt.py
---------------------------
STT plugin using Sarvam AI's saarika-v2 model — built specifically for
Indian languages including Telugu.

Much better Telugu accuracy than generic Whisper because it was trained
on Indic language data.

Get a free API key at: https://dashboard.sarvam.ai
API docs:             https://docs.sarvam.ai/api-reference-docs/speech-to-text
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import wave
from typing import List, Optional

import aiohttp
from livekit.agents import stt
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.rtc import AudioFrame

logger = logging.getLogger("agent.sarvam_stt")

SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"


def _frames_to_wav(frames: List[AudioFrame]) -> bytes:
    """Convert a list of AudioFrames to a WAV bytes object."""
    if not frames:
        return b""

    pcm_data = b"".join(bytes(f.data) for f in frames)
    sample_rate = frames[0].sample_rate
    num_channels = frames[0].num_channels

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)   # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

    return buf.getvalue()


class SarvamSTT(stt.STT):
    """
    STT plugin using Sarvam AI saarika-v2.

    Trained specifically on Indic languages — significantly better Telugu
    accuracy than generic Whisper large-v3.

    Parameters
    ----------
    api_key:  Sarvam API key (defaults to SARVAM_API_KEY env var)
    language: BCP-47 language code, e.g. "te-IN" for Telugu
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        language: str = "te-IN",
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False),
        )
        self._api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self._language = language

        if not self._api_key:
            logger.warning(
                "SARVAM_API_KEY is not set. "
                "Get a free key at https://dashboard.sarvam.ai — "
                "falling back behaviour depends on caller."
            )

    async def _recognize_impl(
        self,
        buffer: "stt.AudioBuffer",
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        """Send accumulated audio to Sarvam API and return transcript."""

        # Normalise buffer → list of AudioFrames
        if hasattr(buffer, "data") and hasattr(buffer, "sample_rate"):
            frames: List[AudioFrame] = [buffer]  # type: ignore[list-item]
        else:
            frames = list(buffer)  # type: ignore[arg-type]

        wav_bytes = _frames_to_wav(frames)
        if not wav_bytes:
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[],
            )

        lang: str = (
            language if language is not NOT_GIVEN else self._language  # type: ignore
        )

        text = await self._call_api(wav_bytes, lang)

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language=lang)],
        )

    async def _call_api(self, wav_bytes: bytes, language: str) -> str:
        """POST wav audio to Sarvam and return the transcript string."""
        headers = {"api-subscription-key": self._api_key}

        form = aiohttp.FormData()
        form.add_field(
            "file",
            wav_bytes,
            filename="audio.wav",
            content_type="audio/wav",
        )
        form.add_field("language_code", language)
        form.add_field("model", "saarika:v2.5")
        form.add_field("with_timestamps", "false")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SARVAM_API_URL,
                    headers=headers,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "Sarvam STT error %d: %s", resp.status, body[:200]
                        )
                        return ""
                    data = await resp.json()
                    text = data.get("transcript", "").strip()
                    if text:
                        logger.info("Sarvam STT: %s", text)
                    return text

        except asyncio.TimeoutError:
            logger.error("Sarvam STT request timed out")
            return ""
        except Exception:
            logger.exception("Sarvam STT request failed")
            return ""
