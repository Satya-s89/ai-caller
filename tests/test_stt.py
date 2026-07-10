"""
tests/test_stt.py
-----------------
Test the Telugu STT service.

Usage
-----
# 1. Basic smoke test (synthetic silent WAV — confirms the endpoint is up):
    python tests/test_stt.py

# 2. Download a real Telugu audio sample from the AI4Bharat dataset, then transcribe:
    python tests/test_stt.py --download

# 3. Transcribe your own audio file:
    python tests/test_stt.py path/to/your_audio.wav

The STT service must be running first:
    cd stt_service && uvicorn main:app --port 8001
"""

from __future__ import annotations

import argparse
import io
import math
import struct
import sys
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

STT_URL = os.getenv("STT_SERVICE_URL", "http://localhost:8001")

# A short Telugu audio sample from the OpenSLR Telugu dataset (public domain)
SAMPLE_AUDIO_URL = (
    "https://www.openslr.org/resources/66/te_in_female.zip"
)
# Direct single-file sample from AI4Bharat's public demo assets
SAMPLE_DIRECT_URL = (
    "https://huggingface.co/datasets/ai4bharat/indicvoices/resolve/main/"
    "samples/te/sample_te_0.wav"
)


def _make_sine_wav(
    freq_hz: float = 440.0,
    duration_s: float = 2.0,
    sample_rate: int = 8000,
) -> bytes:
    """
    Generate a sine-wave WAV (not real speech, but useful for smoke-testing
    the endpoint and audio pipeline without needing a real recording).
    """
    n_frames = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        samples = [
            int(32767 * math.sin(2 * math.pi * freq_hz * i / sample_rate))
            for i in range(n_frames)
        ]
        wf.writeframes(struct.pack(f"<{n_frames}h", *samples))
    buf.seek(0)
    return buf.read()


def _download_sample(out_path: Path) -> bool:
    """Try to download a Telugu speech sample. Returns True on success."""
    print(f"Downloading sample Telugu audio from HuggingFace...")
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(SAMPLE_DIRECT_URL)
            if resp.status_code == 200 and len(resp.content) > 1000:
                out_path.write_bytes(resp.content)
                print(f"Saved sample to: {out_path}")
                return True
    except Exception as exc:
        print(f"Download failed: {exc}")
    return False


def _check_health(base_url: str) -> bool:
    """Check service health and print status."""
    try:
        resp = httpx.get(f"{base_url}/health", timeout=5)
        data = resp.json()
        status_icon = "OK" if data.get("status") == "ok" else "WARN"
        model_icon = "loaded" if data.get("model_loaded") else "NOT LOADED"
        print(f"[{status_icon}] Service health: status={data.get('status')}, model={model_icon}")
        return data.get("status") == "ok"
    except httpx.ConnectError:
        print(f"[ERROR] Cannot connect to STT service at {base_url}")
        print("        Start it with:  cd stt_service && uvicorn main:app --port 8001")
        return False
    except Exception as exc:
        print(f"[ERROR] Health check failed: {exc}")
        return False


def _transcribe(base_url: str, audio_bytes: bytes, filename: str) -> dict | None:
    """Send audio to the STT service and return the result dict."""
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{base_url}/transcribe",
                files={"file": (filename, audio_bytes, "audio/wav")},
            )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
            return None
    except Exception as exc:
        print(f"[ERROR] Request failed: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the Telugu STT service.")
    parser.add_argument(
        "audio_file",
        nargs="?",
        help="Path to an audio file to transcribe (wav/mp3/ogg/flac).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download a Telugu speech sample from HuggingFace and transcribe it.",
    )
    parser.add_argument(
        "--url",
        default=STT_URL,
        help=f"STT service base URL (default: {STT_URL})",
    )
    args = parser.parse_args()

    print(f"STT service : {args.url}")
    print("-" * 50)

    if not _check_health(args.url):
        sys.exit(1)

    print()

    # -- Determine audio source --
    if args.audio_file:
        p = Path(args.audio_file)
        if not p.exists():
            print(f"[ERROR] File not found: {p}")
            sys.exit(1)
        audio_bytes = p.read_bytes()
        filename = p.name
        print(f"Using file : {p} ({len(audio_bytes):,} bytes)")

    elif args.download:
        sample_path = Path(__file__).parent / "sample_te.wav"
        if not _download_sample(sample_path):
            print("Falling back to synthetic sine-wave WAV (model output will be garbage).")
            audio_bytes = _make_sine_wav()
            filename = "sine_test.wav"
        else:
            audio_bytes = sample_path.read_bytes()
            filename = sample_path.name
        print(f"Audio size : {len(audio_bytes):,} bytes")

    else:
        print("No audio file specified — using synthetic 2-second sine-wave WAV.")
        print("(This is a smoke test only; the transcription output will not be real Telugu.)")
        print("Run with --download for a real Telugu sample, or pass a wav file path.")
        audio_bytes = _make_sine_wav()
        filename = "sine_test.wav"

    print()
    print("Sending to STT service...")

    result = _transcribe(args.url, audio_bytes, filename)
    if result is None:
        sys.exit(1)

    print()
    print("=" * 55)
    print(f"  Transcription : {result['text'] or '(empty — silent or non-speech audio)'}")
    print(f"  Language      : {result['language']}")
    print(f"  Duration      : {result['duration_seconds']}s")
    print("=" * 55)


if __name__ == "__main__":
    main()
