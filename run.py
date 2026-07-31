#!/usr/bin/env python3
"""
run.py -- AI Caller single-command launcher
Run from the project root: py run.py
Press Ctrl+C to stop everything cleanly.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT      = Path(__file__).resolve().parent
AGENT_DIR = ROOT / "agent"

# ANSI colours (Windows 10+ supports VT100 natively)
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
YELLOW = "\033[93m"
RED    = "\033[91m"

# Enable ANSI + UTF-8 on Windows
if sys.platform == "win32":
    os.system("")                    # activates VT100
    os.system("chcp 65001 > nul")    # set console code page to UTF-8
    # Reconfigure Python's own stdout/stderr to UTF-8 so Telugu prints cleanly
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_procs: list[tuple[str, str, subprocess.Popen]] = []


def _banner() -> None:
    print(GREEN + BOLD + """
+------------------------------------------------------+
|         AI Caller  -  Telugu Voice Assistant         |
|                                                      |
|  STT : Sarvam saarika-v2.5  (Telugu / Indic)         |
|  LLM : Groq Llama 3.3      (free cloud)              |
|  TTS : Sarvam bulbul:v2     (Telugu / Indic)         |
|  DASH: http://localhost:3000                        |
+------------------------------------------------------+
""" + RESET)


def _prefix(name: str, colour: str) -> str:
    return f"{colour}{BOLD}[{name:<7}]{RESET}"


def _stream_proc(proc: subprocess.Popen, name: str, colour: str) -> None:
    def _read(stream) -> None:
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    print(f"{_prefix(name, colour)} {line}", flush=True)
        except Exception:
            pass

    threading.Thread(target=_read, args=(proc.stdout,), daemon=True).start()
    threading.Thread(target=_read, args=(proc.stderr,), daemon=True).start()


def _launch(name: str, colour: str, cmd: list[str], cwd: Path) -> subprocess.Popen:
    print(f"{_prefix(name, colour)} Starting: {YELLOW}{' '.join(cmd)}{RESET}")
    # Pass UTF-8 encoding env vars so Telugu text logs correctly on Windows
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    _procs.append((name, colour, proc))
    _stream_proc(proc, name, colour)
    return proc


def _shutdown(signum=None, frame=None) -> None:
    print(f"\n{YELLOW}{BOLD}[LAUNCHER] Stopping all services...{RESET}")
    for name, colour, proc in reversed(_procs):
        if proc.poll() is None:
            print(f"{_prefix(name, colour)} Terminating...")
            try:
                proc.terminate()
            except Exception:
                pass
    deadline = time.monotonic() + 5
    for _, _, proc in _procs:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(f"{YELLOW}{BOLD}[LAUNCHER] All services stopped. Bye!{RESET}\n")
    sys.exit(0)


def main() -> None:
    _banner()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # Start the LiveKit agent
    agent_proc = _launch(
        name="AGENT",
        colour=BLUE,
        cmd=[sys.executable, "main.py", "dev"],
        cwd=AGENT_DIR,
    )

    # Start the Call Dashboard server
    dash_proc = _launch(
        name="DASHBOARD",
        colour=GREEN,
        cmd=[sys.executable, str(ROOT / "dashboard" / "app.py")],
        cwd=ROOT,
    )

    print(f"""
{GREEN}All services started!

  Live Call Dashboard:
    http://localhost:3000

  LiveKit Playground:
    https://agents-playground.livekit.io (URL: wss://ai-voice-1a5zwk2f.livekit.cloud)

  Twilio Phone Number:
    +1 517 551 2681

  Press Ctrl+C to stop everything.
{RESET}""")

    try:
        while True:
            if agent_proc.poll() is not None:
                print(f"\n{RED}[LAUNCHER] Agent exited (code {agent_proc.returncode}).{RESET}")
                _shutdown()
            if dash_proc.poll() is not None:
                print(f"\n{YELLOW}[LAUNCHER] Dashboard exited (code {dash_proc.returncode}) — restarting...{RESET}")
                dash_proc = _launch(
                    name="DASHBOARD",
                    colour=GREEN,
                    cmd=[sys.executable, str(ROOT / "dashboard" / "app.py")],
                    cwd=ROOT,
                )
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
