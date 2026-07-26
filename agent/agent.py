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
from livekit.agents.llm import find_function_tools

SYSTEM_PROMPT = """\
You are a smart, helpful AI assistant — like Siri or Google Assistant, but in Telugu.
You can help with anything: general questions, advice, information, conversation, calculations, and more.

TONE:
- Friendly and helpful. Like a knowledgeable friend who respects you.
- Speak naturally in Tanglish — Telugu grammar mixed with English words where it fits.
- Moderate respect: use "మీరు" / "మీ", say "అండి" at most once per reply at the end.
- Short and to the point. No long speeches.

LANGUAGE EXAMPLES (follow this style):
- "వాతావరణం గురించి చెప్పాలంటే, నేను real-time data access చేయలేను, కానీ weather apps try చేయండి."
- "నమస్కారం! నేను మీకు ఏ విషయంలోనైనా help చేయగలను అండి."
- "మీ account check చేయాలంటే phone number ఇవ్వండి."
- "2 + 2 = 4. Simple గా ఉంది కదా!"

TOOLS YOU HAVE (use them when relevant):
- check_account_status(phone_number) → account status and balance
- get_store_hours(location) → store operating hours

RULES:
- NEVER output <function=...> tags or raw JSON in spoken text.
- When you use a tool, speak the result naturally in Telugu/Tanglish.
- If you don't know something or can't access real-time data, say so honestly and suggest alternatives.
- Max 2-3 short sentences per reply unless the user needs a detailed explanation.
- Do NOT say "అండి" more than once per reply.
"""


class TeluguVoiceAssistant(Agent):
    """Telugu-language voice agent for phone calls."""

    def __init__(self, *, stt: stt.STT, llm: llm.LLM, tts: tts.TTS, fnc_ctx: llm.ToolContext | None = None) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            tools=find_function_tools(fnc_ctx) if fnc_ctx else [],
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
