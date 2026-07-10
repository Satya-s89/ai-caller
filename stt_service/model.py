"""
stt_service/model.py
--------------------
Thin wrapper around indic-asr-onnx's IndicTranscriber.
Loaded once at application startup; shared across all requests.

Language code for Telugu: "te"
The ONNX runtime automatically resamples audio to 16 kHz internally.

Audio handling (no pydub, no torchcodec required):
- .wav  -> saved directly to a temp file, read via stdlib wave
- .pcm  -> wrapped in a WAV header (8 kHz, mono, 16-bit) then saved
- other -> converted via ffmpeg subprocess (ffmpeg must be on PATH)

torchaudio 2.11+ dropped all fallback backends and now requires torchcodec
(which in turn needs FFmpeg shared DLLs). We patch torchaudio.load with a
stdlib-only WAV reader so the transcriber works without any extra binaries.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Lazy singleton — populated by load_model()
_transcriber = None

# Formats handled natively (no ffmpeg needed)
_NATIVE = {".wav", ".pcm"}
# Formats that require ffmpeg
_FFMPEG = {".mp3", ".ogg", ".flac", ".m4a", ".webm"}
SUPPORTED_SUFFIXES = _NATIVE | _FFMPEG


# ---------------------------------------------------------------------------
# torchaudio.load patch
# torchaudio 2.11+ defaults to torchcodec backend (needs FFmpeg DLLs).
# We replace torchaudio.load with a pure-stdlib WAV reader so that
# IndicTranscriber.transcribe_ctc() works without any binary deps.
# ---------------------------------------------------------------------------

def _stdlib_wav_load(uri: str, *args, **kwargs):
    """
    Drop-in replacement for torchaudio.load that uses Python's stdlib `wave`.
    Returns (waveform_tensor, sample_rate) — same contract as torchaudio.load.
    Only handles WAV files (all audio is pre-converted to WAV before this call).
    """
    with wave.open(str(uri), "rb") as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()   # bytes per sample
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    if sample_width not in dtype_map:
        raise ValueError(f"Unsupported PCM sample width: {sample_width} bytes")

    samples = np.frombuffer(raw, dtype=dtype_map[sample_width]).copy().astype(np.float32)
    # Normalise to [-1, 1]
    samples /= float(2 ** (sample_width * 8 - 1))
    # Shape: (channels, frames)
    samples = samples.reshape(1, -1) if n_channels == 1 else samples.reshape(-1, n_channels).T
    return torch.from_numpy(samples), sample_rate


def _patch_torchaudio() -> None:
    """Replace torchaudio.load with our stdlib implementation."""
    try:
        import torchaudio
        torchaudio.load = _stdlib_wav_load
        logger.info(
            "Patched torchaudio.load with stdlib wave backend "
            "(torchcodec / FFmpeg DLLs not required)."
        )
    except ImportError:
        logger.warning("torchaudio not installed — skipping patch.")


# ---------------------------------------------------------------------------
# ffmpeg helper
# ---------------------------------------------------------------------------

def _check_ffmpeg() -> bool:
    if shutil.which("ffmpeg") is None:
        logger.warning(
            "ffmpeg not found on PATH — MP3/OGG/FLAC conversion unavailable. "
            "WAV and PCM work fine without it. "
            "Install: winget install ffmpeg  (Windows) | sudo apt install ffmpeg  (Linux)"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Model lifecycle
# ---------------------------------------------------------------------------

def load_model() -> None:
    """Download (first run) and initialise the IndicTranscriber singleton."""
    global _transcriber
    if _transcriber is not None:
        return

    _check_ffmpeg()
    # Patch BEFORE importing IndicTranscriber so torchaudio.load is already
    # replaced when the transcriber module executes torchaudio.load(path).
    _patch_torchaudio()

    logger.info(
        "Loading IndicTranscriber (indic-asr-onnx) — "
        "first run downloads the model (~675 MB), please wait..."
    )
    try:
        from indic_asr_onnx import IndicTranscriber  # type: ignore
        _transcriber = IndicTranscriber()
        logger.info("IndicTranscriber ready.")
    except ImportError as exc:
        raise RuntimeError(
            "indic-asr-onnx not installed. Run: py -m pip install indic-asr-onnx"
        ) from exc
    except Exception as exc:
        logger.error("Failed to load IndicTranscriber: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _bytes_to_wav_tempfile(audio_bytes: bytes, suffix: str) -> str:
    """
    Convert audio bytes to a temporary WAV file.
    Returns the temp file path — caller is responsible for deleting it.
    """
    if suffix == ".wav":
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            return tmp.name

    if suffix == ".pcm":
        # Raw signed 16-bit PCM, 8 kHz, mono (Exotel phone-call format)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(audio_bytes)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(buf.getvalue())
            return tmp.name

    # All other formats — use ffmpeg
    if shutil.which("ffmpeg") is None:
        raise ValueError(
            f"Cannot convert '{suffix}' files: ffmpeg is not installed. "
            "Send WAV or PCM audio, or install ffmpeg."
        )
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(audio_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path + "_out.wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ac", "1", "-f", "wav", tmp_out_path],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise ValueError(
                f"ffmpeg failed to convert '{suffix}': "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
        return tmp_out_path
    finally:
        try:
            os.unlink(tmp_in_path)
        except OSError:
            pass


def _get_wav_duration(wav_path: str) -> float:
    try:
        with wave.open(wav_path, "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    """
    Transcribe raw audio bytes into Telugu text.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio file content (wav, pcm, mp3, ogg, flac, m4a, webm).
    filename : str
        Original filename — used to infer format.

    Returns
    -------
    dict with keys:
        text            : str   — Telugu transcription
        language        : str   — always "te"
        duration_seconds: float — audio duration
    """
    if not audio_bytes:
        raise ValueError("Empty audio input — please send a non-empty audio file.")

    if _transcriber is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    suffix = Path(filename).suffix.lower() or ".wav"

    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported audio format '{suffix}'. "
            f"Supported: {sorted(SUPPORTED_SUFFIXES)}"
        )

    tmp_path: str | None = None
    try:
        tmp_path = _bytes_to_wav_tempfile(audio_bytes, suffix)
        duration_s = _get_wav_duration(tmp_path)

        if duration_s < 0.1:
            raise ValueError(
                f"Audio too short ({duration_s:.3f}s). Send at least 100 ms of audio."
            )

        logger.debug("Transcribing %s (%.2fs)...", filename, duration_s)
        text: str = _transcriber.transcribe_ctc(tmp_path, "te")

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return {
        "text": text.strip(),
        "language": "te",
        "duration_seconds": round(duration_s, 3),
    }
