"""
tts_service/reference/download_reference.py
--------------------------------------------
Downloads a sample Telugu speech WAV to use as the IndicF5 reference voice.

The reference audio is a ~5-second clip of a Telugu speaker. IndicF5 uses
voice cloning to match the speaker's characteristics for synthesis.

Usage:
    py tts_service/reference/download_reference.py

The file is saved as: tts_service/reference/telugu_reference.wav
"""

from __future__ import annotations

import io
import math
import struct
import sys
import wave
from pathlib import Path

OUT_PATH = Path(__file__).parent / "telugu_reference.wav"

# Public-domain Telugu audio samples (try in order)
CANDIDATES = [
    # IndicF5 model repo — may contain sample audio
    "https://huggingface.co/ai4bharat/IndicF5/resolve/main/samples/te_sample.wav",
    "https://huggingface.co/ai4bharat/IndicF5/resolve/main/sample.wav",
    # Shrutilipi Telugu dataset (AI4Bharat, public)
    "https://huggingface.co/datasets/ai4bharat/Shrutilipi/resolve/main/te/sample.wav",
    # AI4Bharat public demo audio
    "https://ai4bharat.iitm.ac.in/assets/audio/te_demo.wav",
    # Mozilla Common Voice single clip (public domain)
    "https://huggingface.co/datasets/mozilla-foundation/common_voice_13_0/resolve/main/audio/te/train/common_voice_te_37513608.wav",
]


def _generate_fallback_wav(path: Path) -> None:
    """
    Generate a 5-second silent WAV as a last resort.
    NOTE: The voice cloning quality will be very poor with silent audio.
    Record a real ~5-second Telugu sentence and replace this file for
    good voice quality.
    """
    sr = 24_000
    n = sr * 5
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        # Very quiet noise (not total silence — some TTS models reject silence)
        import random
        samples = [random.randint(-50, 50) for _ in range(n)]
        wf.writeframes(struct.pack(f"<{n}h", *samples))
    print(f"[WARN] Created placeholder audio at {path}")
    print("       For good voice quality, record a real Telugu speaker")
    print("       saying ~5 seconds of speech and replace this file.")


def main() -> None:
    if OUT_PATH.exists():
        print(f"Reference audio already exists: {OUT_PATH}")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        import httpx
    except ImportError:
        print("httpx not installed. Run: py -m pip install httpx")
        _generate_fallback_wav(OUT_PATH)
        return

    for url in CANDIDATES:
        print(f"Trying: {url} ...")
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200 and len(resp.content) > 10_000:
                    OUT_PATH.write_bytes(resp.content)
                    print(f"[OK] Saved reference audio: {OUT_PATH}")
                    print(f"     Size: {len(resp.content):,} bytes")
                    return
                else:
                    print(f"     HTTP {resp.status_code} or too small, trying next...")
        except Exception as exc:
            print(f"     Failed: {exc}")

    print("\nAll download sources failed. Generating placeholder audio...")
    _generate_fallback_wav(OUT_PATH)


if __name__ == "__main__":
    main()
