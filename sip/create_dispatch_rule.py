"""
sip/create_dispatch_rule.py
----------------------------
Creates a LiveKit SIP dispatch rule routing inbound calls
to the telugu-voice-agent worker room.

Required env vars:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET

Usage:
    py sip/create_dispatch_rule.py --trunk-id <TRUNK_ID>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load env from root directory
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")


def get_livekit_token() -> str:
    """Generate admin token for LiveKit API."""
    try:
        from livekit.api import AccessToken
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.add_grant(room_join=True, room_create=True, admin=True)
        return token.to_jwt()
    except Exception as exc:
        print(f"Failed to generate LiveKit token: {exc}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create LiveKit SIP dispatch rule for Exotel routing."
    )
    parser.add_argument(
        "--trunk-id",
        required=True,
        help="The SIP Trunk ID returned by create_trunk.py",
    )
    args = parser.parse_args()

    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        print("[ERROR] LiveKit credentials not fully set in .env")
        sys.exit(1)

    api_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")

    token = get_livekit_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Dispatch rule payload:
    # Routes any call on this trunk to a room named 'call-{sip_call_id}'.
    # Set the metadata / attributes to target the 'telugu-voice-agent' worker.
    rule_payload = {
        "rule": {
            "name": "Exotel Inbound Route",
            "metadata": "Routes Exotel trunk to Telugu voice agent room",
            "trunk_ids": [args.trunk_id],
            "rule": {
                # Dispatch rule to target room, prefix 'sip-'
                "dispatchRuleDirect": {
                    "room_name": "sip-call",  # Will yield rooms named 'sip-call'
                    "pin": ""                 # No passcode/PIN required to join
                }
            }
        }
    }

    print(f"Connecting to LiveKit REST API at: {api_url}")
    print(f"Creating SIP Dispatch Rule for trunk {args.trunk_id}...")

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/twirp/livekit.SIP/CreateSIPDispatchRule",
                json=rule_payload,
                headers=headers,
            )

        if resp.status_code == 200:
            data = resp.json()
            rule_id = data.get("sip_dispatch_rule_id")
            print()
            print("=" * 60)
            print("  SIP Dispatch Rule Created Successfully! ✓")
            print(f"  Dispatch Rule ID : {rule_id}")
            print("=" * 60)
            print()
            print("Inbound calls on this trunk will now automatically spawn")
            print("a LiveKit room named 'sip-call'.")
        else:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Connection failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
