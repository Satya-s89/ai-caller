"""
agent/plugins/local_stt.py
--------------------------
100% Open-Source Speech-to-Text (STT) plugin for LiveKit Agents.
Uses `faster-whisper` (CTranslate2 optimized Whisper) locally on your machine.

Key Features:
- 100% Free & Open Source (Apache 2.0)
- Zero external cloud dependencies, zero API keys
- Highly accurate for Telugu using whisper-base / medium / large-v3
- High speed via CTranslate2 CPU quantization
- First call auto-downloads the model from Hugging Face (cached thereafter)
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import List, Optional

from livekit.agents import stt
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.rtc import AudioFrame

logger = logging.getLogger("agent.local_stt")


def _frames_to_wav(frames: List[AudioFrame]) -> bytes:
    """Combines a list of 16-bit PCM AudioFrames into a WAV binary in memory."""
    if not frames:
        return b""

    pcm_data = b"".join(bytes(f.data) for f in frames)
    sample_rate = frames[0].sample_rate
    num_channels = frames[0].num_channels

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)  # 16-bit PCM = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

    return buf.getvalue()


class LocalWhisperSTT(stt.STT):
    """
    Local open-source STT using faster-whisper (CTranslate2 Whisper).

    The model is lazy-loaded on the first transcription call and cached
    in memory for the lifetime of the agent process.  Transcription runs
    in a threadpool executor so the async event loop is never blocked.

    Parameters
    ----------
    model_size:
        One of "tiny", "base", "small", "medium", "large-v2", "large-v3".
        "base" downloads ~145 MB and is fast on CPU.
        "medium" downloads ~1.5 GB and is much more accurate.
    device:
        "auto" (default) picks CPU or CUDA automatically.
    compute_type:
        "default" auto-selects; "int8" is fastest on CPU.
    language:
        BCP-47 language code, e.g. "te" for Telugu.
    """

    def __init__(
        self,
        *,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        language: str = "te",
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False),
        )
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model: Optional[object] = None  # lazy-loaded WhisperModel instance

    # ── internal helpers ─────────────────────────────────────────────────────

    async def _load_model(self) -> None:
        """Lazy-load the faster-whisper model on first use."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        logger.info(
            "Loading open-source faster-whisper '%s' on device='%s' compute_type='%s' …",
            self._model_size, self._device, self._compute_type,
        )
        self._model = await asyncio.to_thread(
            WhisperModel,
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        logger.info("faster-whisper model ready ✓")

    # ── LiveKit STT interface ─────────────────────────────────────────────────

    async def _recognize_impl(
        self,
        buffer: "stt.AudioBuffer",
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        """Batch-transcribe an audio buffer using the local faster-whisper model."""
        await self._load_model()

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

        lang: str = language if language is not NOT_GIVEN else self._language  # type: ignore[assignment]

        # Transcription is CPU-bound — run in thread pool to avoid blocking the event loop
        def _transcribe() -> str:
            wav_io = io.BytesIO(wav_bytes)
            segments, _info = self._model.transcribe(  # type: ignore[union-attr]
                wav_io,
                language=lang,
                beam_size=5,
                initial_prompt=(
                    "తెలుగు మాట్లాడే కస్టమర్ కేర్ సహాయకుడు. "
                    "నమస్కారం, ఫోన్ నంబర్, ఖాతా వివరాలు, స్టోర్ సమయాలు."
                ),
            )
            # `segments` is a generator — consume fully inside the thread
            return " ".join(seg.text for seg in segments).strip()

        try:
            text = await asyncio.to_thread(_transcribe)
            if text:
                logger.info("Local STT → %r", text)
            else:
                logger.debug("Local STT returned empty transcript")
        except Exception:
            logger.exception("Local STT transcription failed")
            text = ""

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language=lang)],
        )
