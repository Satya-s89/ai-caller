# ai-caller — Telugu AI Phone Agent

A Telugu-language AI voice agent for inbound phone calls.

**Pipeline:** Exotel (PSTN) → LiveKit SIP bridge → IndicConformer STT → Claude → IndicF5 TTS → Exotel

---

## Project Structure

```
ai-caller/
├── stt_service/     FastAPI wrapping AI4Bharat IndicConformer (STT)  — port 8001
├── tts_service/     FastAPI wrapping AI4Bharat IndicF5 (TTS)         — port 8002
├── agent/           LiveKit Agents worker (STT + Claude + TTS)
├── tests/           Test scripts and local conversation simulator
├── sip/             One-shot scripts: LiveKit SIP trunk + dispatch rule (Stage 5)
├── call_log/        SQLite call log + HTTP viewer (Stage 6)
└── .env.example     All required environment variables (copy → .env)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- `ffmpeg` on PATH (required by pydub for audio decoding)
- LiveKit Cloud account (free tier works)
- Anthropic API key

### 2. Clone and configure

```bash
git clone <this-repo>
cd ai-caller
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY, LIVEKIT_*, etc.
```

### 3. Start the STT service

```bash
cd stt_service
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
# First run downloads IndicConformer ONNX model (~300 MB)
uvicorn main:app --host 0.0.0.0 --port 8001
```

### 4. Start the TTS service

> **Important:** Place your ~5-second Telugu reference audio clip at
> `tts_service/reference/telugu_reference.wav` and update `TTS_REFERENCE_TEXT` in `.env`.

```bash
cd tts_service
python -m venv .venv
.venv\Scripts\activate
# Install PyTorch CPU wheel first:
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
# First run downloads IndicF5 model (~1 GB)
uvicorn main:app --host 0.0.0.0 --port 8002
```

### 5. Run the agent (test room)

```bash
cd agent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py dev
# Opens a LiveKit test room — join from https://meet.livekit.io
```

### 6. Simulate a conversation (no LiveKit required)

```bash
cd tests
python simulate_conversation.py                     # text-mode with default prompts
python simulate_conversation.py my_audio.wav        # WAV-mode
```

---

## Environment Variables

See [`.env.example`](.env.example) for all variables with descriptions.

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | **Free** LLM API key — get at [console.groq.com](https://console.groq.com) |
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL (**free tier** at [cloud.livekit.io](https://cloud.livekit.io)) |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit credentials |
| `STT_SERVICE_URL` | URL of the STT FastAPI service |
| `TTS_SERVICE_URL` | URL of the TTS FastAPI service |
| `TTS_REFERENCE_AUDIO` | Path to reference voice WAV for IndicF5 |
| `TTS_REFERENCE_TEXT` | Transcript of the reference audio clip |
| `CALL_SAMPLE_RATE` | Output audio sample rate (default `8000`) |
| `LOG_LEVEL` | Logging verbosity (`INFO` / `DEBUG`) |

---

## Build Stages

| Stage | Description | Status |
|---|---|---|
| 1 | Project scaffold | ✅ Done |
| 2 | Telugu STT service | ✅ Done |
| 3 | Telugu TTS service | ✅ Done |
| 4 | LiveKit agent | ✅ Done |
| 5 | Exotel SIP integration | ✅ Done |
| 6 | Call log & polish | ✅ Done |

---

## Running the Call Log Viewer

All inbound calls, caller phone numbers, call durations, and complete Telugu transcripts are automatically saved in a local SQLite database (`call_log/calls.db`).

You can view the recent call history and transcripts directly in your CLI using:
```powershell
py call_log/viewer.py
```

---

## Stage 5 — Exotel Setup Instructions

1. **Enable SIP trunking**: Log in to your Exotel dashboard and ensure you have a VoIP gateway/SIP trunk enabled.
2. **Obtain inbound SIP details**: In the Exotel dashboard → **SIP Settings**, register your LiveKit SIP URI (e.g. `your-project.livekit.cloud`) as the outbound SIP destination.
3. **Register the Trunk in LiveKit**: Run the script to create the inbound trunk on the LiveKit side:
   ```powershell
   py sip/create_trunk.py
   ```
4. **Link rules**: Create the rule directing calls on that trunk to the `telugu-voice-agent` room:
   ```powershell
   py sip/create_dispatch_rule.py --trunk-id <TRUNK_ID>
   ```

---

## License

MIT