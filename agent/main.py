"""
agent/main.py
-------------
LiveKit agent entrypoint.

Wires IndicSTT → Groq/Llama 3.3 (FREE) → IndicTTS into an AgentSession.
Logs call metadata and transcripts to local SQLite database on shutdown.

Run:
    cd agent
    py main.py dev
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from livekit.agents import AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli, TurnHandlingOptions
from livekit.agents.inference import VAD
from livekit.plugins import groq

from agent import TeluguVoiceAssistant, AssistantTools
from plugins.indic_stt import IndicSTT
from plugins.indic_tts import IndicTTS
from call_log.db import log_call_start, log_call_end

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent.main")


async def entrypoint(ctx: JobContext) -> None:
    logger.info("Agent joining room: %s", ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Detect SIP caller from remote participants
    caller_phone = "Unknown"
    for participant in ctx.room.remote_participants.values():
        identity = participant.identity or ""
        if "sip" in identity.lower():
            caller_phone = identity.replace("sip_", "")
            break

    # Log call start
    log_call_start(call_id=ctx.room.name, caller_phone=caller_phone)
    logger.info("Call started — room: %s, caller: %s", ctx.room.name, caller_phone)

    # Instantiate plugins
    stt_instance = IndicSTT()
    llm_instance = groq.LLM(model="llama-3.3-70b-versatile")
    tts_instance = IndicTTS()
    vad_instance = VAD(
        min_speech_duration=0.2,
        min_silence_duration=0.6,
        activation_threshold=0.5,
    )

    # Pass plugins to the agent constructor
    fnc_ctx = AssistantTools()
    agent = TeluguVoiceAssistant(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        fnc_ctx=fnc_ctx,
    )
    # The agent class uses the VAD from session or agent property
    agent._vad = vad_instance

    session = AgentSession(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        vad=vad_instance,
    )

    await session.start(room=ctx.room, agent=agent)
    logger.info("AgentSession started in room: %s", ctx.room.name)

    # Register shutdown callback — called automatically when the room disconnects
    async def on_shutdown(reason: str) -> None:
        logger.info("Call ended (reason: %s) — room: %s", reason, ctx.room.name)

        # Extract transcript from session history
        transcript = []
        try:
            # session.chat_ctx is the ChatContext object in 1.6.x
            for msg in session.chat_ctx.messages:
                role = getattr(msg, "role", "")
                content = getattr(msg, "text_content", "") or getattr(msg, "content", "")
                if role and content:
                    transcript.append({"role": str(role), "content": str(content)})
        except Exception as exc:
            logger.warning("Could not extract transcript: %s", exc)

        log_call_end(call_id=ctx.room.name, transcript=transcript)

    ctx.add_shutdown_callback(on_shutdown)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="telugu-voice-agent",
        )
    )
