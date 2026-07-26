# ai-caller — Telugu AI Phone Agent

A real-time Telugu-language AI voice agent that answers actual phone calls via **Twilio + LiveKit**.

**Pipeline:** Twilio (+1 517 551 2681) → LiveKit SIP → Sarvam STT → Groq LLaMA → Sarvam TTS

---

## Features

- 🎙️ **Telugu STT**: Sarvam `saarika:v2.5` — built for Indic languages
- 🤖 **LLM**: Groq Llama 3.3 70B — free, fast cloud inference  
- 🔊 **Telugu TTS**: Sarvam `bulbul:v2` — natural Indian Telugu voice
- 📞 **Real Phone Calls**: Twilio SIP → LiveKit bridge
- 📊 **Live Dashboard**: `http://localhost:3000` — call history & transcripts
- 🧠 **Tanglish**: Natural Telugu + English code-switching

---

## Project Structure

```
ai-caller/
├── agent/
│   ├── main.py           # LiveKit agent entry point
│   ├── agent.py          # System prompt + tool definitions
│   ├── plugins/
│   │   ├── sarvam_stt.py # Sarvam AI STT (primary, Telugu-native)
│   │   ├── local_stt.py  # faster-whisper fallback (offline)
│   │   └── indic_tts.py  # Sarvam TTS / Edge TTS streaming
│   └── requirements.txt
├── dashboard/
│   ├── app.py            # aiohttp dashboard server (port 3000)
│   └── static/
│       └── index.html    # Live call monitoring UI
├── call_log/
│   ├── db.py             # SQLite call log helpers
│   └── calls.db          # Auto-created on first call
├── crm/
│   └── db.py             # Customer lookup
├── sip/
│   ├── fix_sip.py        # One-shot: clean + recreate SIP trunk
│   ├── create_trunk.py   # Create LiveKit inbound trunk
│   └── create_dispatch_rule.py
├── deploy/
│   ├── setup.sh          # Automated Ubuntu/Debian server setup
│   ├── ai-caller.service # systemd unit for 24/7 service
│   └── README.md         # Server deployment guide
├── tests/
├── run.py                # Single-command launcher
├── .env                  # API keys (never commit!)
└── .env.example          # Template for .env
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **API keys** (all free tier):
  - [Groq](https://console.groq.com) — LLM
  - [Sarvam AI](https://dashboard.sarvam.ai) — STT + TTS
  - [LiveKit Cloud](https://cloud.livekit.io) — WebRTC/SIP
  - [Twilio](https://twilio.com) — Phone calls

### 2. Clone & configure

```bash
git clone https://github.com/Satya-s89/ai-caller.git
cd ai-caller
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/Mac
```

Edit `.env` and fill in your API keys.

### 3. Install dependencies

```bash
cd agent
pip install -r requirements.txt
cd ..
pip install -r requirements.txt
```

### 4. Run everything

```bash
py run.py
```

This starts:
- **AI Agent** — connects to LiveKit, waits for calls
- **Dashboard** — live call viewer at `http://localhost:3000`

### 5. Test via browser (no phone number needed)

Open [LiveKit Playground](https://agents-playground.livekit.io) and connect with:
- **URL**: `wss://ai-voice-1a5zwk2f.livekit.cloud`
- **Agent**: `telugu-voice-agent`

### 6. Test via real phone call

Call **`+1 517 551 2681`** from your Twilio-verified number.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ | LLM — free at [console.groq.com](https://console.groq.com) |
| `SARVAM_API_KEY` | ✅ | STT + TTS — free at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| `LIVEKIT_URL` | ✅ | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | ✅ | LiveKit API key |
| `LIVEKIT_API_SECRET` | ✅ | LiveKit API secret |
| `STT_PROVIDER` | optional | `sarvam` (default) \| `groq` \| `local` |
| `SARVAM_TTS_SPEAKER` | optional | `meera` (default) \| `pavithra` |
| `TTS_VOICE` | optional | Edge TTS voice (fallback) — `te-IN-ShrutiNeural` |
| `LOG_LEVEL` | optional | `INFO` (default) \| `DEBUG` |
| `DASHBOARD_PORT` | optional | Dashboard port — default `3000` |

---

## Telephony Setup (One-time)

After configuring your Twilio Elastic SIP Trunk and linking your phone number:

```bash
# Reset and create clean LiveKit SIP trunk + dispatch rule
py sip/fix_sip.py
```

This handles:
1. Deletes any old/conflicting trunks from LiveKit
2. Creates a new inbound trunk for `+15175512681`
3. Creates the dispatch rule routing to `telugu-voice-agent`

---

## Deploy to Server (24/7)

See [`deploy/README.md`](deploy/README.md) for Oracle Cloud / VPS deployment.

```bash
chmod +x deploy/setup.sh
./deploy/setup.sh
sudo systemctl start ai-caller
```

---

## License

MIT