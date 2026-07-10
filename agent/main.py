"""
agent/main.py
-------------
LiveKit agent entrypoint.

Starts a worker that:
  1. Connects to a LiveKit room (assigned by the server / dispatch rule).
  2. Wires IndicSTT → Groq/Llama 3.3 (FREE) → IndicTTS into an AgentSession.

Run locally (test room):
    cd agent
    python main.py dev

Run as a persistent worker (production):
    python main.py start

Environment variables required (all in ../.env):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    GROQ_API_KEY          (free at https://console.groq.com)
    STT_SERVICE_URL, TTS_SERVICE_URL
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from livekit.agents import AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import groq

from agent import TeluguVoiceAssistant
from plugins.indic_stt import IndicSTT
from plugins.indic_tts import IndicTTS

logger = logging.getLogger("agent.main")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("Agent joining room: %s", ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        stt=IndicSTT(),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),  # FREE via Groq
        tts=IndicTTS(),
    )

    await session.start(room=ctx.room, agent=TeluguVoiceAssistant())
    logger.info("AgentSession started in room: %s", ctx.room.name)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="telugu-voice-agent",   # used by SIP dispatch rule in Stage 5
        )
    )
