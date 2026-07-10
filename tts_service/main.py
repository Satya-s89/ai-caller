"""
tts_service/main.py
--------------------
FastAPI service wrapping Edge TTS (Microsoft Speech API) for Telugu text-to-speech.
This provides INSTANT (under 0.5s) responses on CPUs/laptops, using soundfile
to decode MP3 to WAV without needing ffmpeg.

Endpoints
---------
GET  /health       -> {"status": "ok", "service": "tts", "model_loaded": True}
POST /synthesize   -> JSON body: {"text": str, "sample_rate": int (optional, 8000)}
                     Returns: audio/wav binary
"""

from __future__ import annotations

import io
import logging
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
import edge_tts
import soundfile as sf
import numpy as np

# Load from the project root .env
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tts_service")

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(
    title="Telugu TTS Service",
    description="Uses Edge TTS for instant, high-quality Telugu voice synthesis.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class SynthesizeRequest(BaseModel):
    text: str = Field(
        ...,
        description="Telugu text to synthesize.",
    )
    sample_rate: int = Field(
        default=8000,
        ge=8000,
        le=48000,
        description="Output audio sample rate in Hz. 8000 = phone-call standard.",
    )


@app.get("/health", tags=["ops"])
async def health():
    return {
        "status": "ok",
        "service": "tts",
        "model_loaded": True,
    }


@app.post("/synthesize", tags=["tts"], response_class=Response)
async def synthesize_endpoint(req: SynthesizeRequest):
    if not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text is empty.",
        )

    logger.info("Synthesize (Edge-TTS): %d chars @ %d Hz — %s", len(req.text), req.sample_rate, req.text[:60])

    try:
        # Generate speech using Edge-TTS (using the high-quality Shruti Telugu neural voice)
        communicate = edge_tts.Communicate(req.text, "te-IN-ShrutiNeural")
        
        # Accumulate MP3 audio bytes from the stream
        mp3_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_data += chunk["data"]

        if not mp3_data:
            raise RuntimeError("Edge-TTS returned no audio data")

        # Decode MP3 bytes using soundfile
        data, native_sr = sf.read(io.BytesIO(mp3_data))

        # Ensure mono channel (1D array)
        if len(data.shape) > 1:
            data = data[:, 0]

        # We no longer resample in Python to avoid metallic artifacts and quality loss.
        # Native Edge TTS sample rate is typically 24000 Hz. LiveKit will auto-resample.
        data_to_write = data
        output_sr = native_sr

        # Write to WAV bytes with the native sample rate
        wav_io = io.BytesIO()
        sf.write(wav_io, data_to_write, output_sr, format='WAV', subtype='PCM_16')
        wav_bytes = wav_io.getvalue()

        logger.info("Synthesized %d bytes of audio via Edge-TTS (native %d Hz)", len(wav_bytes), output_sr)
        return Response(content=wav_bytes, media_type="audio/wav")

    except Exception as exc:
        logger.exception("Edge-TTS synthesis error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synthesis failed: {exc}",
        ) from exc
