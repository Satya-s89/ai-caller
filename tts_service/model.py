"""
tts_service/model.py
--------------------
Thin wrapper around Meta's MMS-TTS (facebook/mms-tts-tel) for Telugu TTS.
This is a completely free, ungated model — no HuggingFace login required.
Loaded once at application startup; shared across all requests.

Model: facebook/mms-tts-tel (~50 MB, VITS architecture)
  - Native sample rate: 16 kHz
  - Outputs: clean Telugu speech
  - No voice cloning (consistent neutral voice)
  - CPU-friendly, fast inference

Reference audio is NOT required — model has a built-in Telugu voice.
"""

from __future__ import annotations

import io
import logging
import re
import wave
from math import gcd
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Model config
MODEL_ID = "facebook/mms-tts-tel"   # Telugu MMS TTS (ungated, free)
NATIVE_SR = 16_000                  # MMS TTS native output sample rate
MAX_CHUNK_CHARS = 200

_model = None
_tokenizer = None


def load_model() -> None:
    """Download (first run) and initialise the MMS TTS model singleton."""
    global _model, _tokenizer

    if _model is not None:
        return

    logger.info(
        "Loading MMS TTS (%s) — first run downloads ~50 MB, please wait...",
        MODEL_ID,
    )
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, VitsModel  # type: ignore

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = VitsModel.from_pretrained(MODEL_ID)
        _model.eval()
        logger.info("MMS TTS ready. Model: %s, native SR: %d Hz", MODEL_ID, NATIVE_SR)
    except ImportError as exc:
        raise RuntimeError(
            "transformers not installed. Run: py -m pip install transformers"
        ) from exc
    except Exception as exc:
        logger.error("Failed to load MMS TTS: %s", exc)
        raise


def _chunk_text(text: str) -> list[str]:
    """Split long text at sentence boundaries to avoid VITS length limits."""
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= MAX_CHUNK_CHARS:
            current = (current + " " + sent).strip()
        else:
            if current:
                chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks or [text]


def _write_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    """Write a float32 numpy array as 16-bit PCM WAV bytes."""
    pcm = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (pcm * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    buf.seek(0)
    return buf.read()


def synthesize(text: str, target_sr: int = 8000) -> bytes:
    """
    Convert Telugu text to speech audio using MMS TTS.

    Parameters
    ----------
    text : str
        Telugu text (may include Telugu-English code-mixing).
    target_sr : int
        Output sample rate in Hz (default 8 000 for phone calls).

    Returns
    -------
    bytes
        16-bit PCM WAV file at the requested sample rate.
    """
    if not text.strip():
        raise ValueError("Empty text input.")

    if _model is None or _tokenizer is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    import torch  # type: ignore
    from scipy.signal import resample_poly  # type: ignore

    chunks = _chunk_text(text)
    all_audio: list[np.ndarray] = []

    for i, chunk in enumerate(chunks):
        logger.debug("Synthesizing chunk %d/%d: %s", i + 1, len(chunks), chunk[:50])
        try:
            inputs = _tokenizer(chunk, return_tensors="pt")
            with torch.no_grad():
                output = _model(**inputs)
            # output.waveform shape: (1, num_samples)
            arr = output.waveform[0].cpu().numpy().astype(np.float32)
            all_audio.append(arr)
        except Exception as exc:
            logger.error("Chunk %d failed: %s", i + 1, exc)
            raise

    audio = np.concatenate(all_audio) if all_audio else np.zeros(NATIVE_SR, dtype=np.float32)

    # Resample from NATIVE_SR (16kHz) to target_sr (8kHz) if needed
    if target_sr != NATIVE_SR:
        g = gcd(NATIVE_SR, target_sr)
        audio = resample_poly(audio, target_sr // g, NATIVE_SR // g).astype(np.float32)

    return _write_wav(audio, target_sr)
