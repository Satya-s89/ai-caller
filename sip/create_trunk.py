"""
sip/create_trunk.py
--------------------
Creates a LiveKit SIP Inbound Trunk for Twilio Elastic SIP Trunking.
Run ONCE after you have set up your Twilio SIP Trunk.

Required env vars (in .env):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET

Usage:
    py sip/create_trunk.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# Twilio's SIP edge locations that send calls to us
# See: https://www.twilio.com/docs/sip-trunking/regions
TWILIO_SIP_ADDRESSES = [
    "pstn.twilio.com",
    "sip.twilio.com",
]


async def main() -> None:
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
    print("Creating Twilio inbound SIP trunk in LiveKit...")

    try:
        from livekit.protocol.sip import (  # type: ignore
            CreateSIPInboundTrunkRequest,
            SIPInboundTrunkInfo,
        )

        req = CreateSIPInboundTrunkRequest(
            trunk=SIPInboundTrunkInfo(
                name="Twilio Inbound Trunk",
                metadata="Routes Twilio calls to Telugu AI voice agent",
                allowed_addresses=TWILIO_SIP_ADDRESSES,
            )
        )
        trunk = await lk.sip.create_inbound_trunk(req)

        print()
        print("=" * 60)
        print("  SIP Inbound Trunk Created! ✓")
        print(f"  Trunk ID : {trunk.sip_trunk_id}")
        print(f"  Name     : {trunk.name}")
        print("=" * 60)
        print()
        print("NEXT STEP — create the dispatch rule:")
        print(f"  py sip/create_dispatch_rule.py --trunk-id {trunk.sip_trunk_id}")
        print()
        print("ALSO — configure Twilio SIP Trunk to send calls to:")
        print("  sip.livekit.cloud  (LiveKit's SIP endpoint)")

    except Exception as exc:
        print(f"[ERROR] Failed to create trunk: {type(exc).__name__}: {exc}")
        sys.exit(1)
    finally:
        await lk.aclose()


if __name__ == "__main__":
    asyncio.run(main())
