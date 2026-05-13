import httpx
from openai import AsyncOpenAI

from app.config import get_settings


async def transcribe(recording_url: str) -> tuple[str, str]:
    """Fetch Twilio recording audio and transcribe via Whisper. Returns (raw_text, model_name).

    Caller must discard raw_text immediately after redaction — it must never be stored.
    """
    settings = get_settings()
    model = "whisper-1"

    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{recording_url}.mp3",
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
        )
        resp.raise_for_status()
        audio_bytes = resp.content

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    result = await client.audio.transcriptions.create(
        model=model,
        file=("recording.mp3", audio_bytes, "audio/mpeg"),
    )
    return result.text, model
