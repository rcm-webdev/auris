import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_claude_response(payload: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(payload))]
    return msg


@pytest.mark.asyncio
async def test_extract_returns_structured_outcome():
    expected = {
        "summary": "Prospect expressed interest in a Q3 follow-up.",
        "disposition": "callback",
        "next_action": "Schedule call for July",
    }
    with patch("app.services.extraction.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_claude_response(expected))
        mock_cls.return_value = mock_client

        from app.services.extraction import extract
        result = await extract("Hello [REDACTED], calling about your account.")

    assert result["summary"] == expected["summary"]
    assert result["disposition"] == "callback"
    assert result["next_action"] == "Schedule call for July"


@pytest.mark.asyncio
async def test_extract_handles_null_next_action():
    expected = {
        "summary": "Left a voicemail.",
        "disposition": "voicemail",
        "next_action": None,
    }
    with patch("app.services.extraction.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_claude_response(expected))
        mock_cls.return_value = mock_client

        from app.services.extraction import extract
        result = await extract("You've reached [REDACTED], please leave a message.")

    assert result["disposition"] == "voicemail"
    assert result["next_action"] is None
