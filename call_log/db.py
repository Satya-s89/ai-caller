"""
call_log/db.py
--------------
SQLite call log database management.
Creates database, tables, and provides functions to log call metadata and transcripts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "calls.db"


def init_db() -> None:
    """Initialize the SQLite database and create the calls table if it doesn't exist."""
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                caller_phone TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_seconds REAL,
                transcript TEXT  -- JSON encoded conversation history
            )
            """
        )
        conn.commit()


def log_call_start(call_id: str, caller_phone: str) -> None:
    """Log the start of a call."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        start_time = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT OR REPLACE INTO calls (call_id, caller_phone, start_time, transcript)
            VALUES (?, ?, ?, ?)
            """,
            (call_id, caller_phone, start_time, json.dumps([])),
        )
        conn.commit()


def log_call_end(call_id: str, transcript: list[dict]) -> None:
    """Log the completion of a call, calculating duration and saving the final transcript."""
    init_db()
    end_time_dt = datetime.now()
    end_time = end_time_dt.isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Retrieve start_time to calculate duration
        cursor.execute("SELECT start_time FROM calls WHERE call_id = ?", (call_id,))
        row = cursor.fetchone()
        duration = 0.0
        if row and row[0]:
            try:
                start_time_dt = datetime.fromisoformat(row[0])
                duration = (end_time_dt - start_time_dt).total_seconds()
            except ValueError:
                pass

        cursor.execute(
            """
            UPDATE calls
            SET end_time = ?, duration_seconds = ?, transcript = ?
            WHERE call_id = ?
            """,
            (end_time, duration, json.dumps(transcript, ensure_ascii=False), call_id),
        )
        conn.commit()


def get_all_calls() -> list[dict]:
    """Retrieve all logged calls from the database."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM calls ORDER BY start_time DESC")
        rows = cursor.fetchall()
        calls = []
        for r in rows:
            try:
                tx = json.loads(r["transcript"])
            except Exception:
                tx = []
            calls.append(
                {
                    "call_id": r["call_id"],
                    "caller_phone": r["caller_phone"],
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                    "duration_seconds": r["duration_seconds"],
                    "transcript": tx,
                }
            )
        return calls
