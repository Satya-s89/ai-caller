import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

async def fix():
    from livekit import api as lk_api
    lk = lk_api.LiveKitAPI(url=LIVEKIT_URL, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    trunks = await lk.sip.list_inbound_trunk(lk_api.ListSIPInboundTrunkRequest())
    rules = await lk.sip.list_dispatch_rule(lk_api.ListSIPDispatchRuleRequest())

    # Delete existing rules first
    for r in rules.items:
        print(f"Deleting rule {r.sip_dispatch_rule_id}...")
        await lk.sip.delete_dispatch_rule(lk_api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=r.sip_dispatch_rule_id))

    # Delete existing trunks
    for t in trunks.items:
        print(f"Deleting trunk {t.sip_trunk_id}...")
        await lk.sip.delete_trunk(lk_api.DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id))

    print("\nCreating new clean Twilio Inbound Trunk (with all number variants + Twilio addresses)...")
    from livekit.protocol.sip import (
        CreateSIPInboundTrunkRequest,
        SIPInboundTrunkInfo,
        CreateSIPDispatchRuleRequest,
        SIPDispatchRule,
        SIPDispatchRuleDirect,
    )

    # Match all possible number formats Twilio might send (+15175512681, 15175512681, etc.)
    new_trunk = await lk.sip.create_inbound_trunk(
        CreateSIPInboundTrunkRequest(
            trunk=SIPInboundTrunkInfo(
                name="Twilio Inbound Trunk",
                metadata="Twilio +15175512681",
                numbers=["+15175512681", "15175512681", "5175512681"],
                allowed_addresses=["pstn.twilio.com", "sip.twilio.com"],
            )
        )
    )
    print(f"✅ Created Trunk ID: {new_trunk.sip_trunk_id}")

    new_rule = await lk.sip.create_dispatch_rule(
        CreateSIPDispatchRuleRequest(
            name="Twilio Route to Telugu Agent",
            trunk_ids=[new_trunk.sip_trunk_id],
            rule=SIPDispatchRule(
                dispatch_rule_direct=SIPDispatchRuleDirect(
                    room_name="sip-call",
                    pin="",
                )
            ),
        )
    )
    print(f"✅ Created Dispatch Rule ID: {new_rule.sip_dispatch_rule_id}")
    print("\n✨ SIP configuration fixed cleanly for Twilio!")
    await lk.aclose()

if __name__ == "__main__":
    asyncio.run(fix())
