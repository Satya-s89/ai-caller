"""
dashboard/app.py
----------------
Live Call Dashboard Server using aiohttp.web.
Provides web UI & REST endpoints to monitor active/past calls and transcripts.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from aiohttp import web

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from call_log.db import get_all_calls, get_call_by_id

logger = logging.getLogger("dashboard")
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def handle_index(request: web.Request) -> web.FileResponse:
    """Serve the single page dashboard application."""
    index_file = STATIC_DIR / "index.html"
    return web.FileResponse(index_file)


async def api_get_calls(request: web.Request) -> web.Response:
    """API endpoint to get call history list."""
    calls = get_all_calls()
    return web.json_response({"status": "success", "calls": calls})


async def api_get_call_detail(request: web.Request) -> web.Response:
    """API endpoint to get transcript & details for a specific call."""
    call_id = request.match_info.get("call_id", "")
    call = get_call_by_id(call_id)
    if not call:
        return web.json_response({"status": "error", "message": "Call not found"}, status=404)
    return web.json_response({"status": "success", "call": call})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/calls", api_get_calls)
    app.router.add_get("/api/calls/{call_id}", api_get_call_detail)
    app.router.add_static("/static", STATIC_DIR)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Railway sets PORT automatically; fall back to DASHBOARD_PORT or 3000
    base_port = int(os.getenv("PORT") or os.getenv("DASHBOARD_PORT", "3000"))
    for p in range(base_port, base_port + 10):
        try:
            print(f"🚀 Call Dashboard starting at http://localhost:{p}")
            web.run_app(create_app(), host="0.0.0.0", port=p, print=None)
            break
        except OSError as e:
            if e.errno in (10048, 98):
                continue
            raise
