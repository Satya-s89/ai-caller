"""
agent/agent.py
--------------
Defines the TeluguVoiceAssistant Agent with its system prompt.
Wired into an AgentSession in main.py.
"""

from __future__ import annotations

from livekit.agents import Agent
from livekit.agents import stt, tts, llm

SYSTEM_PROMPT = (
    "You are a highly polite, respectful, and professional customer service assistant speaking Telugu. "
    "Use formal and respectful language appropriate for telephone calls. "
    "Always address the caller with respect (use 'మీరు', 'చెప్పండి', 'సహాయపడగలను' instead of informal 'నువ్వు', 'చెప్పు'). "
    "When greeting, always say 'నమస్కారం అండి' or 'నమస్తే అండి'. NEVER say 'నమస్తే మీరు' or 'నమస్కారం మీరు'. "
    "For example, start with: 'నమస్కారం అండి, నేను మీకు ఎలా సహాయపడగలను?' "
    "Keep responses short, helpful, concise, and conversational. "
    "Avoid any slang or grammatically awkward phrasing. "
    "Do not use markdown formatting — speak in plain sentences only."
)


class TeluguVoiceAssistant(Agent):
    """Telugu-language voice agent for phone calls."""

    def __init__(self, *, stt: stt.STT, llm: llm.LLM, tts: tts.TTS) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
        )
