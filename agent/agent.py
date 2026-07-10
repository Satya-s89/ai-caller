"""
agent/agent.py
--------------
Defines the TeluguVoiceAssistant Agent with its system prompt.
Wired into an AgentSession in main.py.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger("agent.tools")

class AssistantTools(llm.ToolContext):
    """Tools for the Telugu Voice Assistant."""

    def __init__(self):
        super().__init__([])

    @llm.function_tool(description="Gets the account status for a given phone number.")
    async def check_account_status(
        self,
        phone_number: str,
    ) -> str:
        """Called when the user asks about their account status or account standing."""
        logger.info(f"Checking account status for {phone_number}")
        # Mock logic
        if phone_number.endswith("9999"):
            return "The account is suspended due to unpaid dues."
        return "The account is active and in good standing."

    @llm.function_tool(description="Gets the operating hours for a specific store location.")
    async def get_store_hours(
        self,
        location: str,
    ) -> str:
        """Called when the user asks when a store opens or closes."""
        logger.info(f"Getting store hours for {location}")
        # Mock logic
        return f"The store at {location} is open from 9 AM to 9 PM, Monday through Saturday."
