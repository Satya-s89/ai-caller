"""
tests/simulate_conversation.py
--------------------------------
Local end-to-end test harness — no LiveKit room, no real phone call.

Simulates a multi-turn conversation by:
  1. Loading a list of pre-recorded Telugu audio clips (or text prompts).
  2. Sending each through STT → Groq/Llama 3.3 (FREE) → TTS.
  3. Printing the transcript and saving each TTS response to disk.

Usage:
    # Both services must be running first:
    #   stt_service: uvicorn main:app --port 8001
    #   tts_service: uvicorn main:app --port 8002

    python tests/simulate_conversation.py

    # Or pass a list of WAV files representing caller utterances:
    python tests/simulate_conversation.py turn1.wav turn2.wav
"""

from __future__ import annotations

import asyncio
import io
import os
import struct
import sys
import wave
from pathlib import Path

import httpx
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

STT_URL = os.getenv("STT_SERVICE_URL", "http://localhost:8001")
TTS_URL = os.getenv("TTS_SERVICE_URL", "http://localhost:8002")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"  # FREE via Groq

SYSTEM_PROMPT = (
    "You are a helpful assistant who speaks Telugu naturally, "
    "including common Telugu-English code-mixing. "
    "Keep responses short and conversational, appropriate for a phone call. "
    "Do not use markdown formatting — speak in plain sentences only."
)

# Fallback text prompts used when no WAV files are supplied
DEFAULT_TURNS = [
    "నమస్కారం, మీరు ఎలా ఉన్నారు?",
    "నాకు రేపటి వాతావరణం గురించి చెప్పగలరా?",
    "ధన్యవాదాలు, అంతా అయిపోయింది.",
]


def _make_silent_wav(duration_s: float = 0.5, sr: int = 8000) -> bytes:
    n = int(sr * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *([0] * n)))
    buf.seek(0)
    return buf.read()


async def stt(client: httpx.AsyncClient, audio_bytes: bytes, filename: str) -> str:
    resp = await client.post(
        f"{STT_URL}/transcribe",
        files={"file": (filename, audio_bytes, "audio/wav")},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["text"]


async def tts(client: httpx.AsyncClient, text: str, out_path: Path) -> None:
    resp = await client.post(
        f"{TTS_URL}/synthesize",
        json={"text": text, "sample_rate": 8000},
        timeout=120,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def llm_reply(groq_client: Groq, history: list[dict], user_text: str) -> str:
    history.append({"role": "user", "content": user_text})
    response = groq_client.chat.completions.create(
        model=MODEL,
        max_tokens=256,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
        ],
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return reply


async def run(wav_paths: list[Path]) -> None:
    groq_client = Groq(api_key=GROQ_API_KEY)
    history: list[dict] = []
    out_dir = Path(__file__).parent / "sim_output"
    out_dir.mkdir(exist_ok=True)

    async with httpx.AsyncClient() as client:
        for i, wav_path in enumerate(wav_paths):
            print(f"\n{'─'*60}")
            print(f"Turn {i+1}")

            if wav_path.name.startswith("__text__:"):
                # Text-mode turn (no WAV)
                user_text = wav_path.name[len("__text__:"):]
                print(f"[TEXT INPUT] {user_text}")
            else:
                audio_bytes = wav_path.read_bytes()
                print(f"[STT] Transcribing {wav_path.name} …")
                user_text = await stt(client, audio_bytes, wav_path.name)
                print(f"[STT] → {user_text}")

            print("[LLM] Thinking …")
            reply = llm_reply(groq_client, history, user_text)
            print(f"[LLM] → {reply}")

            out_wav = out_dir / f"turn_{i+1:02d}_response.wav"
            print(f"[TTS] Synthesizing → {out_wav.name} …")
            await tts(client, reply, out_wav)
            print(f"[TTS] Saved: {out_wav}")

    print(f"\n{'='*60}")
    print(f"Simulation complete. {len(wav_paths)} turns. Output: {out_dir}")


def main() -> None:
    if len(sys.argv) > 1:
        wav_paths = [Path(p) for p in sys.argv[1:]]
    else:
        # Text-mode: create fake Path objects with encoded text
        print("No WAV files supplied — running in text-mode with default Telugu prompts.")
        wav_paths = [Path(f"__text__:{t}") for t in DEFAULT_TURNS]

    asyncio.run(run(wav_paths))


if __name__ == "__main__":
    main()
