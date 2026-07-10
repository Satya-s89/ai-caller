"""
tts_service/main.py
--------------------
FastAPI service wrapping AI4Bharat IndicF5 for Telugu text-to-speech.

Endpoints
---------
GET  /health       -> {"status": "ok", "service": "tts", "model_loaded": bool}
POST /synthesize   -> JSON body: {"text": str, "sample_rate": int (optional, 8000)}
                     Returns: audio/wav binary

Start with:
    cd tts_service
    uvicorn main:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load from the project root .env (one level up from tts_service/)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# -- Logging --
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tts_service")

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from model import load_model, synthesize  # noqa: E402


# -- Lifespan --
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


# -- App --
app = FastAPI(
    title="Telugu TTS Service",
    description=(
        "Wraps AI4Bharat IndicF5 for Telugu text-to-speech synthesis. "
        "Uses voice cloning from a reference audio clip. "
        "Returns audio/wav at the requested sample rate."
    ),
    version="0.1.0",
    lifespan=lifespan,
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
        description="Telugu text to synthesize (may include Telugu-English code-mixing).",
    )
    sample_rate: int = Field(
        default=8000,
        ge=8000,
        le=48000,
        description="Output audio sample rate in Hz. 8000 = phone-call standard.",
    )


@app.get("/health", tags=["ops"])
async def health():
    """Health check — also reports whether the model has been loaded."""
    from model import _model
    return {
        "status": "ok",
        "service": "tts",
        "model_loaded": _model is not None,
    }


@app.post("/synthesize", tags=["tts"], response_class=Response)
async def synthesize_endpoint(req: SynthesizeRequest):
    """
    Synthesize Telugu speech from text.

    Returns an `audio/wav` binary response.
    Long text is automatically chunked at sentence boundaries.

    **Example:**
    ```json
    {"text": "నమస్కారం, మీరు ఎలా ఉన్నారు?", "sample_rate": 8000}
    ```
    """
    if not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text is empty.",
        )

    logger.info("Synthesize: %d chars @ %d Hz — %s", len(req.text), req.sample_rate, req.text[:60])

    try:
        wav_bytes = synthesize(req.text, target_sr=req.sample_rate)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
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
        logger.exception("Unexpected synthesis error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synthesis failed: {type(exc).__name__}: {exc}",
        ) from exc

    logger.info("Synthesized %d bytes of audio", len(wav_bytes))
    return Response(content=wav_bytes, media_type="audio/wav")
