"""
stt_service/main.py
--------------------
FastAPI service wrapping AI4Bharat IndicConformer (via indic-asr-onnx).

Endpoints
---------
GET  /health         -> {"status": "ok", "service": "stt", "model_loaded": bool}
POST /transcribe     -> multipart/form-data with field "file" (audio)
                       Returns: {"text": str, "language": "te", "duration_seconds": float}
GET  /docs           -> Swagger UI (auto-generated)

Start with:
    cd stt_service
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load from the project root .env (one level up from stt_service/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# -- Logging --
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stt_service")

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import after dotenv so LOG_LEVEL is set
from model import load_model, transcribe_audio  # noqa: E402


# -- Lifespan (load model at startup) --
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


# -- App --
app = FastAPI(
    title="Telugu STT Service",
    description=(
        "Wraps AI4Bharat IndicConformer (indic-asr-onnx) for Telugu speech-to-text. "
        "Accepts audio files in WAV/PCM/MP3/OGG/FLAC format and returns transcribed Telugu text."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the LiveKit agent (running locally on a different port) to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
async def health():
    """Health check — also reports whether the model has been loaded."""
    from model import _transcriber
    return {
        "status": "ok",
        "service": "stt",
        "model_loaded": _transcriber is not None,
    }


@app.post("/transcribe", tags=["stt"])
async def transcribe(file: UploadFile = File(...)):
    """
    Transcribe a Telugu audio file to text.

    **Accepted formats:** wav, pcm, mp3, ogg, flac, m4a, webm

    **Phone-call audio:** 8 kHz, mono, 16-bit PCM WAV (matches Exotel output).
    The model internally resamples to 16 kHz.

    **Returns:**
    ```json
    {
      "text": "నమస్కారం",
      "language": "te",
      "duration_seconds": 1.234
    }
    ```
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No filename in upload. Set a Content-Disposition filename.",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    logger.info("Received: %s (%d bytes)", file.filename, len(audio_bytes))

    try:
        result = transcribe_audio(audio_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {type(exc).__name__}: {exc}",
        ) from exc

    logger.info(
        "Transcribed %.2fs audio -> %d chars: %s",
        result["duration_seconds"],
        len(result["text"]),
        result["text"][:60] + ("..." if len(result["text"]) > 60 else ""),
    )
    return JSONResponse(content=result)
