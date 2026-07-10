"""
call_log/viewer.py
------------------
Interactive CLI call log viewer.
Lists all recent calls and prints complete transcripts.

Usage:
    py call_log/viewer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to python path to resolve local imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from call_log.db import get_all_calls


def main() -> None:
    calls = get_all_calls()
    if not calls:
        print("No calls found in database.")
        return

    print("=" * 70)
    print(f"  Telugu Voice Agent Call Log Viewer ({len(calls)} calls)")
    print("=" * 70)

    for i, call in enumerate(calls, 1):
        print(f"\n[{i}] Call ID: {call['call_id']}")
        print(f"    Caller Phone : {call['caller_phone'] or 'Unknown'}")
        print(f"    Start Time   : {call['start_time']}")
        print(f"    End Time     : {call['end_time'] or 'Active/Interrupted'}")
        print(f"    Duration     : {call['duration_seconds'] or 0.0:.2f} seconds")

        tx = call["transcript"]
        if tx:
            print("    Transcript   :")
            for turn in tx:
                role = "Caller" if turn.get("role") == "user" else "Agent"
                print(f"      - {role}: {turn.get('content')}")
        else:
            print("    Transcript   : None")
        print("-" * 70)


if __name__ == "__main__":
    main()
