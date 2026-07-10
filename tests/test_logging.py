"""
tests/test_logging.py
---------------------
Smoke test for the database call logger and CLI viewer.
Inserts a mock call and lists it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to python path to resolve local imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from call_log.db import log_call_start, log_call_end
from call_log.viewer import main as run_viewer


def test_logging() -> None:
    print("Testing call logging database writes...")
    mock_call_id = "test-sip-call-12345"
    mock_phone = "919876543210"
    mock_transcript = [
        {"role": "user", "content": "నమస్కారం, మీరు ఎలా ఉన్నారు?"},
        {"role": "assistant", "content": "నమస్కారం! నేను బాగున్నాను. మీకు ఎలా సహాయం చేయగలను?"},
        {"role": "user", "content": "ధన్యవాదాలు, అంతా అయిపోయింది."},
        {"role": "assistant", "content": "ధన్యవాదాలు! సెలవు."},
    ]

    # Log call start
    log_call_start(mock_call_id, mock_phone)
    print("✓ Logged call start")

    # Log call end
    log_call_end(mock_call_id, mock_transcript)
    print("✓ Logged call end and transcript")

    # Run viewer to inspect the log output
    print("\nRunning viewer output test:")
    run_viewer()


if __name__ == "__main__":
    test_logging()
