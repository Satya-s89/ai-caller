"""
sip/create_trunk.py
--------------------
Creates a LiveKit SIP inbound trunk for Exotel.
Run after you have configured your trunk in LiveKit / Exotel.

Required env vars:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    EXOTEL_SIP_URI   e.g. sip:your-account@sip.exotel.com

Usage:
    py sip/create_trunk.py
"""

from __future__ import annotations

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
EXOTEL_SIP_URI = os.getenv("EXOTEL_SIP_URI", "")


def get_livekit_token() -> str:
    """Generate admin token for LiveKit API."""
    try:
        from livekit.api import AccessToken
        # Create token with admin/SIP permissions
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.add_grant(room_join=True, room_create=True, admin=True)
        # Convert LiveKit token to JWT representation
        return token.to_jwt()
    except Exception as exc:
        print(f"Failed to generate LiveKit token: {exc}")
        sys.exit(1)


def main() -> None:
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        print("[ERROR] LiveKit credentials not fully set in .env")
        sys.exit(1)

    # Clean the HTTP/HTTPS scheme to get the base domain for REST API
    # e.g., wss://project.livekit.cloud -> https://project.livekit.cloud
    api_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")

    # Generate Authorization Header token
    token = get_livekit_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Inbound trunk configuration for Exotel
    # Since we want Exotel to route to us, we define an inbound SIP trunk.
    trunk_payload = {
        "trunk": {
            "name": "Exotel Inbound Trunk",
            "numbers": [],  # Leave empty to accept any incoming numbers, or specify yours
            "metadata": "Exotel telephone integration trunk",
            "inbound_addresses": [
                # Exotel SIP server IPs (or domain)
                "sip.exotel.com",
            ],
        }
    }

    print(f"Connecting to LiveKit REST API at: {api_url}")
    print("Creating inbound SIP trunk...")

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{api_url}/twirp/livekit.SIP/CreateSIPInboundTrunk",
                json=trunk_payload,
                headers=headers,
            )

        if resp.status_code == 200:
            data = resp.json()
            trunk = data.get("trunk", {})
            print()
            print("=" * 60)
            print("  SIP Inbound Trunk Created Successfully! ✓")
            print(f"  Trunk ID : {trunk.get('sip_trunk_id')}")
            print(f"  Name     : {trunk.get('name')}")
            print("=" * 60)
            print()
            print("Copy the Trunk ID above to use with the dispatch rule script:")
            print(f"  py sip/create_dispatch_rule.py --trunk-id {trunk.get('sip_trunk_id')}")
        else:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] Connection failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
