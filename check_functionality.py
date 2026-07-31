"""
check_functionality.py
Verifies all modules import correctly and key functions work.
Run from project root: py check_functionality.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

errors = []
passed = []

def ok(msg): passed.append(msg); print(f"  [PASS] {msg}")
def fail(msg, e): errors.append(msg); print(f"  [FAIL] {msg}: {e}")

print("\n=== 1. Module Imports ===")
try:
    from call_log.db import get_all_calls, get_call_by_id, log_call_start, log_call_end
    ok("call_log.db")
except Exception as e:
    fail("call_log.db", e)

try:
    import crm.db
    ok("crm.db")
except Exception as e:
    fail("crm.db", e)

try:
    from plugins.indic_tts import IndicTTS, _tts_to_pcm, _edge_tts_to_pcm, _sarvam_tts_to_pcm
    ok("plugins.indic_tts")
except Exception as e:
    fail("plugins.indic_tts", e)

try:
    from plugins.sarvam_stt import SarvamSTT
    ok("plugins.sarvam_stt")
except Exception as e:
    fail("plugins.sarvam_stt", e)

try:
    from plugins.local_stt import LocalWhisperSTT
    ok("plugins.local_stt")
except Exception as e:
    fail("plugins.local_stt", e)

try:
    from agent import TeluguVoiceAssistant, AssistantTools
    ok("agent (TeluguVoiceAssistant + AssistantTools)")
except Exception as e:
    fail("agent", e)

try:
    from dashboard.app import create_app
    ok("dashboard.app")
except Exception as e:
    fail("dashboard.app", e)


print("\n=== 2. CRM Database ===")
try:
    import crm.db
    c = crm.db.get_customer_status("1234567890")
    assert c is not None, "Customer not found"
    assert c["name"] == "John Doe", f"Unexpected name: {c['name']}"
    ok(f"get_customer_status → {c['name']} / {c['account_status']}")
except Exception as e:
    fail("get_customer_status", e)

try:
    s = crm.db.get_store_info("Hyderabad")
    assert s is not None, "Store not found"
    ok(f"get_store_info → {s['location']} {s['open_time']}-{s['close_time']}")
except Exception as e:
    fail("get_store_info", e)


print("\n=== 3. Call Log Database ===")
try:
    from call_log.db import log_call_start, log_call_end, get_call_by_id
    test_id = "__test_call__"
    log_call_start(test_id, "+91999")
    log_call_end(test_id, [{"role": "user", "content": "test"}])
    record = get_call_by_id(test_id)
    assert record is not None, "Record not found after write"
    assert record["caller_phone"] == "+91999"
    assert len(record["transcript"]) == 1
    ok(f"log_call_start / log_call_end / get_call_by_id round-trip")
except Exception as e:
    fail("call_log round-trip", e)


print("\n=== 4. Tool Methods (no external calls) ===")
import asyncio
try:
    from agent import AssistantTools
    tools = AssistantTools()
    result = asyncio.run(tools.get_current_time())
    assert "202" in result, f"Unexpected time result: {result}"
    ok(f"get_current_time → {result[:50]}")
except Exception as e:
    fail("get_current_time", e)

try:
    result = asyncio.run(tools.send_followup_sms("+919999999999", "Test message"))
    assert "successfully" in result.lower()
    ok(f"send_followup_sms → {result[:60]}")
except Exception as e:
    fail("send_followup_sms", e)

try:
    result = asyncio.run(tools.check_account_status("1234567890"))
    assert "John Doe" in result
    ok(f"check_account_status → {result[:60]}")
except Exception as e:
    fail("check_account_status", e)

try:
    result = asyncio.run(tools.get_store_hours("Hyderabad"))
    assert "9:00" in result
    ok(f"get_store_hours → {result[:60]}")
except Exception as e:
    fail("get_store_hours", e)


print("\n=== 5. TTS Instantiation ===")
try:
    tts = IndicTTS()
    ok(f"IndicTTS() created (streaming={tts.capabilities.streaming})")
except Exception as e:
    fail("IndicTTS instantiation", e)

try:
    stt = SarvamSTT(language="te-IN")
    ok(f"SarvamSTT() created (key set={bool(os.getenv('SARVAM_API_KEY'))})")
except Exception as e:
    fail("SarvamSTT instantiation", e)


print("\n=== 6. Environment Variables ===")
required = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GROQ_API_KEY"]
for var in required:
    val = os.getenv(var, "")
    if val:
        ok(f"{var} = {val[:8]}...")
    else:
        fail(f"{var}", "NOT SET — agent will not start")

optional = ["SARVAM_API_KEY", "STT_PROVIDER", "DASHBOARD_PORT"]
for var in optional:
    val = os.getenv(var, "")
    status = f"{val[:12]}..." if val else "(not set — will use fallback)"
    ok(f"{var} = {status}")


print(f"\n{'='*40}")
print(f"Results: {len(passed)} passed, {len(errors)} failed")
if errors:
    print(f"FAILED: {errors}")
else:
    print("All checks passed! ✓")
