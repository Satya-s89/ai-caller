"""
agent/agent.py
--------------
Defines the TeluguVoiceAssistant Agent with its system prompt.
Wired into an AgentSession in main.py.
"""

from livekit.agents import Agent

SYSTEM_PROMPT = (
    "You are a helpful assistant who speaks Telugu naturally, "
    "including common Telugu-English code-mixing. "
    "Keep responses short and conversational, appropriate for a phone call. "
    "Do not use markdown formatting — speak in plain sentences only."
)


class TeluguVoiceAssistant(Agent):
    """Telugu-language voice agent for phone calls."""

    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
