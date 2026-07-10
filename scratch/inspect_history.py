import livekit.agents
from livekit.agents import AgentSession
from livekit.plugins import groq
from plugins.indic_stt import IndicSTT
from plugins.indic_tts import IndicTTS
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

# Let's inspect history property of AgentSession
print("AgentSession.history:", AgentSession.history)
print("Type of AgentSession.history:", type(AgentSession.history))

# Let's create dummy instance
# Or look at its signature or source code if possible
import inspect
try:
    print(inspect.getsource(AgentSession.history.fget))
except Exception as e:
    print("Error getting source:", e)
