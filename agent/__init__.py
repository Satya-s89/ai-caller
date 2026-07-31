# agent package — re-export core classes from agent.agent submodule.
# This allows `from agent import TeluguVoiceAssistant` to work whether
# the caller's cwd is the project root (where `agent` is a package) or
# the agent/ directory (where `agent` resolves to agent.py directly).
from agent.agent import TeluguVoiceAssistant, AssistantTools

__all__ = ["TeluguVoiceAssistant", "AssistantTools"]
