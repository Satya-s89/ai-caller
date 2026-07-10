import livekit.agents
import inspect

print("Livekit Agents Version:", livekit.agents.__version__)
from livekit.agents import AgentSession
print("AgentSession methods:")
for name, member in inspect.getmembers(AgentSession):
    if not name.startswith('_'):
        print(f" - {name}: {type(member)}")
