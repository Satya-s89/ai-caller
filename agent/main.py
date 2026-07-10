"""
agent/main.py
-------------
LiveKit agent entrypoint.

Starts a worker that:
  1. Connects to a LiveKit room (assigned by the server / dispatch rule).
  2. Wires IndicSTT → Groq/Llama 3.3 (FREE) → IndicTTS into an AgentSession.
  3. Logs call metadata and transcripts to local SQLite database.

Run locally (test room):
    cd agent
    py main.py dev

Run as a persistent worker (production):
    py main.py start
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to python path to resolve local imports (like call_log)
sys.path.append(str(Path(__file__).resolve().parent.parent))

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from livekit.agents import AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.plugins import groq

from agent import TeluguVoiceAssistant
from plugins.indic_stt import IndicSTT
from plugins.indic_tts import IndicTTS
from call_log.db import log_call_start, log_call_end

logger = logging.getLogger("agent.main")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("Agent joining room: %s", ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Detect if there's a SIP caller participant
    caller_phone = "Unknown"
    for participant in ctx.room.active_participants.values():
        identity = participant.identity
        if identity.startswith("sip_") or "sip" in identity.lower():
            caller_phone = identity.replace("sip_", "")
            break

    # Log call start in SQLite
    log_call_start(call_id=ctx.room.name, caller_phone=caller_phone)

    session = AgentSession(
        stt=IndicSTT(),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),  # FREE via Groq
        tts=IndicTTS(),
    )

    await session.start(room=ctx.room, agent=TeluguVoiceAssistant())
    logger.info("AgentSession started in room: %s", ctx.room.name)

    # Wait for the session / room to close
    while ctx.room.is_connected:
        await asyncio.sleep(1)

    # Fetch conversation history on disconnect
    transcript = []
    try:
        # Get history from AgentSession conversation object
        history = session.conversation.get_history()
        for msg in history:
            transcript.append({
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.text or "",
            })
    except Exception as exc:
        logger.error("Failed to extract conversation history: %s", exc)

    # Log call end
    log_call_end(call_id=ctx.room.name, transcript=transcript)
    logger.info("AgentSession ended and logged for room: %s", ctx.room.name)


if __name__ == "__main__":
    import asyncio  # required for sleep loop in entrypoint
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="telugu-voice-agent",   # used by SIP dispatch rule
        )
    )
