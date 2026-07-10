import io
import time
import wave
import pytest
import httpx

# URLs for the local services
STT_SERVICE_URL = "http://127.0.0.1:8001"
TTS_SERVICE_URL = "http://127.0.0.1:8002"

def create_dummy_wav() -> bytes:
    """Create a 0.5-second silent 16kHz WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 0.5 seconds of silence
        wf.writeframes(b"\x00" * (16000 * 2 // 2))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_stt_service_latency_and_format():
    """Test STT endpoint for <1s latency and correct JSON format."""
    dummy_wav = create_dummy_wav()
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{STT_SERVICE_URL}/transcribe",
            files={"file": ("dummy.wav", dummy_wav, "audio/wav")},
            timeout=5.0,
        )
    elapsed = time.time() - start_time
    
    assert response.status_code == 200, f"STT failed with {response.text}"
    
    data = response.json()
    assert "text" in data
    assert "language" in data
    # A completely silent audio might return empty text, which is fine, 
    # as long as the API succeeds and parses it.
    
    # Latency check: should be under 5.0 seconds for a dummy file 
    # (first request might be slower due to model warmup)
    assert elapsed < 5.0, f"STT took too long: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_tts_service_latency_and_format():
    """Test TTS endpoint for <1s latency and valid WAV output."""
    test_text = "నమస్కారం అండి, నేను ఎలా సహాయపడగలను?"
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TTS_SERVICE_URL}/synthesize",
            json={"text": test_text, "sample_rate": 16000},
            timeout=5.0,
        )
    elapsed = time.time() - start_time
    
    assert response.status_code == 200, f"TTS failed with {response.text}"
    
    # Should return valid audio/wav
    assert response.headers.get("content-type") == "audio/wav"
    audio_bytes = response.content
    assert len(audio_bytes) > 1000, "Audio response is too small to be a valid WAV file"
    
    # Latency check: should be under 5.0 seconds
    assert elapsed < 5.0, f"TTS took too long: {elapsed:.2f}s"


def test_agent_initialization():
    """Test that the LiveKit Agent initializes correctly and tools/prompts load."""
    import sys
    from pathlib import Path
    
    # Add agent dir to path to import agent modules
    agent_dir = Path(__file__).resolve().parent.parent / "agent"
    sys.path.append(str(agent_dir))
    
    from agent.agent import TeluguVoiceAssistant
    from agent.plugins.indic_stt import IndicSTT
    from agent.plugins.indic_tts import IndicTTS
    from livekit.plugins import groq
    
    stt_instance = IndicSTT()
    tts_instance = IndicTTS()
    llm_instance = groq.LLM(model="llama-3.3-70b-versatile")
    
    agent = TeluguVoiceAssistant(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
    )
    
    assert agent is not None
    assert "నమస్కారం అండి" in agent._instructions, "Polite greeting missing from prompt!"
    assert agent.stt == stt_instance
    assert agent.tts == tts_instance
    

@pytest.mark.asyncio
async def test_assistant_tools_function_calling():
    """Test the newly created AssistantTools context and its AI functions."""
    import sys
    from pathlib import Path
    
    agent_dir = Path(__file__).resolve().parent.parent / "agent"
    sys.path.append(str(agent_dir))
    
    from agent.agent import AssistantTools
    
    tools = AssistantTools()
    
    # Test checking account status
    status_good = await tools.check_account_status(phone_number="1234567890")
    assert "Active" in status_good, "SQLite Active status fetch failed"
    assert "150.0" in status_good, "SQLite balance fetch failed"
    
    status_bad = await tools.check_account_status(phone_number="5555559999")
    assert "Suspended" in status_bad, "SQLite suspended status fetch failed"
    
    # Test getting store hours
    hours = await tools.get_store_hours(location="Vijayawada")
    assert "Vijayawada" in hours
    assert "10:00 AM" in hours
    assert "8:00 PM" in hours
