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

from livekit.agents import AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.inference import VAD
from livekit.plugins import groq

from agent import TeluguVoiceAssistant, AssistantTools
from plugins.indic_tts import IndicTTS
from plugins.local_stt import LocalWhisperSTT
from plugins.sarvam_stt import SarvamSTT
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

    # ── STT ─────────────────────────────────────────────────────────────────
    # Priority: sarvam (best Telugu) → groq whisper → local faster-whisper
    stt_provider = os.getenv("STT_PROVIDER", "sarvam").lower()

    if stt_provider == "sarvam" and os.getenv("SARVAM_API_KEY"):
        logger.info("STT: Sarvam saarika-v2 (best Telugu accuracy)")
        stt_instance = SarvamSTT(language="te-IN")

    elif stt_provider == "local":
        logger.info("STT: faster-whisper (local)")
        stt_instance = LocalWhisperSTT(model_size="medium", language="te")

    else:
        # Groq Whisper fallback (or when SARVAM_API_KEY not set)
        if stt_provider == "sarvam":
            logger.warning("SARVAM_API_KEY not set — falling back to Groq Whisper")
        logger.info("STT: Groq whisper-large-v3 (cloud, Telugu + English)")
        stt_instance = groq.STT(
            model="whisper-large-v3",
            language="te",
            prompt=(
                "తెలుగు customer care call. Tanglish conversation. "
                "నమస్కారం. account status. balance. phone number. "
                "store timings. ఖాతా. active. inactive. rupees. "
                "hello. hi. what can you do. thank you. store hours."
            ),
        )

    # ── LLM ─────────────────────────────────────────────────────────────────
    # 70b handles Telugu/Tanglish far better than 8b — quality > micro-speed gain
    llm_instance = groq.LLM(model="llama-3.3-70b-versatile")

    # ── TTS ─────────────────────────────────────────────────────────────────
    tts_instance = IndicTTS()

    # ── VAD ─────────────────────────────────────────────────────────────────
    # min_speech_duration=0.3  → require 300ms of real speech before triggering STT
    #                            (prevents Whisper from hallucinating on breath/noise)
    # min_silence_duration=0.4 → wait 400ms of silence before processing
    #                            (gives user time to finish their sentence)
    # activation_threshold=0.6 → slightly higher so background noise doesn't trigger
    vad_instance = VAD(
        min_speech_duration=0.3,
        min_silence_duration=0.4,
        activation_threshold=0.6,
    )

    # Pass plugins to the agent constructor
    fnc_ctx = AssistantTools()
    agent = TeluguVoiceAssistant(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        fnc_ctx=fnc_ctx,
    )

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
            # Try different attribute paths for LiveKit 1.6.x compatibility
            messages = []
            if hasattr(session, 'chat_ctx') and session.chat_ctx is not None:
                messages = getattr(session.chat_ctx, 'messages', [])
            elif hasattr(session, '_activity') and session._activity is not None:
                chat_ctx = getattr(session._activity, 'chat_ctx', None)
                if chat_ctx:
                    messages = getattr(chat_ctx, 'items', [])
            for msg in messages:
                role = getattr(msg, 'role', '')
                content = getattr(msg, 'text_content', '') or getattr(msg, 'content', '')
                if role and content:
                    transcript.append({'role': str(role), 'content': str(content)})
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
