import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.transcription import transcribe


@pytest.mark.asyncio
async def test_transcribe_returns_text_and_model():
    mock_audio = b"fake-audio-bytes"
    mock_text = "Hello, this is a test transcript."

    mock_http_resp = MagicMock()
    mock_http_resp.content = mock_audio
    mock_http_resp.raise_for_status = MagicMock()

    mock_whisper_resp = MagicMock()
    mock_whisper_resp.text = mock_text

    with (
        patch("app.services.transcription.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.transcription.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_http_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_openai = AsyncMock()
        mock_openai.audio.transcriptions.create = AsyncMock(return_value=mock_whisper_resp)
        mock_openai_cls.return_value = mock_openai

        text, model = await transcribe("https://api.twilio.com/Recordings/RE123")

    assert text == mock_text
    assert model == "whisper-1"


@pytest.mark.asyncio
async def test_transcribe_appends_mp3_extension():
    mock_http_resp = MagicMock()
    mock_http_resp.content = b"audio"
    mock_http_resp.raise_for_status = MagicMock()

    mock_whisper_resp = MagicMock()
    mock_whisper_resp.text = "test"

    captured_url = []

    with (
        patch("app.services.transcription.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.transcription.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_http = AsyncMock()
        async def fake_get(url, **kwargs):
            captured_url.append(url)
            return mock_http_resp
        mock_http.get = fake_get
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_openai = AsyncMock()
        mock_openai.audio.transcriptions.create = AsyncMock(return_value=mock_whisper_resp)
        mock_openai_cls.return_value = mock_openai

        await transcribe("https://api.twilio.com/Recordings/RE123")

    assert captured_url[0].endswith(".mp3")
