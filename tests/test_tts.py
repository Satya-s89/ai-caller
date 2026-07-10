"""
tests/test_tts.py
-----------------
Test the Telugu TTS service.

Usage
-----
# 1. Basic smoke test (synthesizes a short Telugu greeting):
    py tests/test_tts.py

# 2. Synthesize a custom text:
    py tests/test_tts.py "మీరు చెప్పిన పని చేస్తాను"

The TTS service must be running first:
    cd tts_service && py -m uvicorn main:app --port 8002
"""

from __future__ import annotations

import io
import os
import sys
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

TTS_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8002")

DEFAULT_TEXT = "నమస్కారం! నేను మీకు ఎలా సహాయం చేయగలను?"


def _check_health(base_url: str) -> bool:
    try:
        resp = httpx.get(f"{base_url}/health", timeout=5)
        data = resp.json()
        model_status = "loaded" if data.get("model_loaded") else "NOT loaded"
        icon = "OK" if data.get("status") == "ok" else "WARN"
        print(f"[{icon}] TTS service: status={data.get('status')}, model={model_status}")
        return data.get("status") == "ok"
    except httpx.ConnectError:
        print(f"[ERROR] Cannot connect to TTS service at {base_url}")
        print("        Start it with:  cd tts_service && py -m uvicorn main:app --port 8002")
        return False
    except Exception as exc:
        print(f"[ERROR] Health check failed: {exc}")
        return False


def _synthesize(base_url: str, text: str, sample_rate: int = 8000) -> bytes | None:
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(
                f"{base_url}/synthesize",
                json={"text": text, "sample_rate": sample_rate},
            )
        if resp.status_code == 200:
            return resp.content
        print(f"[ERROR] HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    except Exception as exc:
        print(f"[ERROR] Request failed: {exc}")
        return None


def _wav_duration(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def main() -> None:
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEXT

    print(f"TTS service : {TTS_URL}")
    print("-" * 50)

    if not _check_health(TTS_URL):
        sys.exit(1)

    print()
    print(f"Input text  : {text}")
    print("Synthesizing... (may take 20-60s on first call)")

    wav_bytes = _synthesize(TTS_URL, text)
    if wav_bytes is None:
        sys.exit(1)

    out_path = Path(__file__).parent / "sim_output" / "tts_test.wav"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_bytes(wav_bytes)

    duration = _wav_duration(wav_bytes)
    print()
    print("=" * 55)
    print(f"  Output WAV  : {out_path}")
    print(f"  Size        : {len(wav_bytes):,} bytes")
    print(f"  Duration    : {duration:.2f}s")
    print("=" * 55)
    print()
    print("Open the WAV file to listen to the synthesized Telugu speech.")


if __name__ == "__main__":
    main()
