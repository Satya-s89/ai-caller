"""
sip/create_dispatch_rule.py
----------------------------
Creates a LiveKit SIP dispatch rule routing inbound Exotel calls
to the telugu-voice-agent worker room.

Required env vars (in .env):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET

Usage:
    py sip/create_dispatch_rule.py --trunk-id <TRUNK_ID>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")


async def main(trunk_id: str) -> None:
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        print("[ERROR] LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET must be set in .env")
        sys.exit(1)

    try:
        from livekit import api as lk_api
    except ImportError:
        print("[ERROR] livekit-api not installed. Run: py -m pip install livekit-api")
        sys.exit(1)

    lk = lk_api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    print(f"Connecting to: {LIVEKIT_URL}")
    print(f"Creating SIP Dispatch Rule for trunk: {trunk_id} ...")

    try:
        from livekit.protocol.sip import (  # type: ignore
            CreateSIPDispatchRuleRequest,
            SIPDispatchRule,
            SIPDispatchRuleDirect,
        )

        req = CreateSIPDispatchRuleRequest(
            name="Exotel→Telugu Agent Route",
            metadata="Routes inbound Exotel calls to the Telugu voice agent room",
            trunk_ids=[trunk_id],
            rule=SIPDispatchRule(
                dispatch_rule_direct=SIPDispatchRuleDirect(
                    room_name="sip-call",
                    pin="",  # No PIN required
                )
            ),
        )
        rule = await lk.sip.create_sip_dispatch_rule(req)

        print()
        print("=" * 60)
        print("  SIP Dispatch Rule Created Successfully! ✓")
        print(f"  Rule ID  : {rule.sip_dispatch_rule_id}")
        print(f"  Name     : {rule.name}")
        print("=" * 60)
        print()
        print("All done! Inbound calls on this trunk will spawn a LiveKit")
        print("room named 'sip-call' and be handled by the Telugu agent.")

    except Exception as exc:
        print(f"[ERROR] Failed to create dispatch rule: {type(exc).__name__}: {exc}")
        sys.exit(1)
    finally:
        await lk.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trunk-id", required=True, help="Trunk ID from create_trunk.py")
    args = parser.parse_args()
    asyncio.run(main(args.trunk_id))
