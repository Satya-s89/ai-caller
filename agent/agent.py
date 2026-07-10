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

    def __init__(self, *, stt: stt.STT, llm: llm.LLM, tts: tts.TTS, fnc_ctx: llm.ToolContext | None = None) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            tools=[fnc_ctx] if fnc_ctx else [],
        )

logger = logging.getLogger("agent.tools")

class AssistantTools(llm.ToolContext):
    """Tools for the Telugu Voice Assistant."""

    def __init__(self):
        super().__init__([])

    @llm.function_tool(description="Gets the account status and balance for a given phone number.")
    async def check_account_status(
        self,
        phone_number: str,
    ) -> str:
        """Called when the user asks about their account status, balance, or standing."""
        logger.info(f"Checking account status for {phone_number}")
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parent.parent))
        import crm.db
        
        customer = crm.db.get_customer_status(phone_number)
        if not customer:
            return f"I could not find an account associated with the phone number {phone_number}."
            
        status = customer["account_status"]
        balance = customer["balance"]
        name = customer["name"]
        
        return f"The account for {name} is currently '{status}' with a balance of ${balance}."

    @llm.function_tool(description="Gets the operating hours for a specific store location.")
    async def get_store_hours(
        self,
        location: str,
    ) -> str:
        """Called when the user asks when a store opens or closes."""
        logger.info(f"Getting store hours for {location}")
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).resolve().parent.parent))
        import crm.db
        
        store = crm.db.get_store_info(location)
        if not store:
            return f"I could not find a store location matching {location}."
            
        open_time = store["open_time"]
        close_time = store["close_time"]
        return f"The {store['location']} store is open from {open_time} to {close_time}."
