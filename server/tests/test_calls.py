from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_session
from app.main import app

FAKE_USER = {"id": "user1", "name": "Test User", "email": "test@example.com"}

FAKE_CALL_ROW = {
    "id": "call-uuid-1",
    "twilio_call_sid": "CA123",
    "recording_url": "https://api.twilio.com/rec",
    "duration_seconds": 120,
    "called_at": datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
    "status": "extracted",
    "agent_id": "agent-uuid-1",
    "agent_name": "Jane Smith",
    "redacted_text": "Hello [REDACTED], calling about your account.",
    "whisper_model": "whisper-1",
    "summary": "Prospect expressed interest",
    "disposition": "callback",
    "next_action": "Schedule follow-up",
}

FAKE_AUDIT_ROW = {
    "id": "audit-uuid-1",
    "event": "transcription_completed",
    "actor": "system",
    "metadata": None,
    "created_at": datetime(2026, 5, 1, 12, 1, 0, tzinfo=timezone.utc),
}


@pytest.fixture(autouse=True)
def mock_pool():
    app.state.pool = MagicMock()


@pytest.fixture
def auth():
    async def override():
        return FAKE_USER
    app.dependency_overrides[get_current_session] = override
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_calls_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/calls")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_calls_returns_shape(auth, monkeypatch):
    monkeypatch.setattr(
        "app.api.calls.storage.list_calls",
        AsyncMock(return_value=([{
            "id": "call-uuid-1",
            "twilio_call_sid": "CA123",
            "duration_seconds": 90,
            "called_at": datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
            "status": "extracted",
            "agent_id": "agent-uuid-1",
            "agent_name": "Jane Smith",
        }], 1)),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/calls")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "total" in body and "page" in body and "limit" in body
    assert body["total"] == 1
    item = body["data"][0]
    assert item["agent"] == {"id": "agent-uuid-1", "name": "Jane Smith"}


@pytest.mark.asyncio
async def test_get_call_not_found(auth, monkeypatch):
    monkeypatch.setattr("app.api.calls.storage.get_call", AsyncMock(return_value=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/calls/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_call_returns_nested_shape(auth, monkeypatch):
    monkeypatch.setattr("app.api.calls.storage.get_call", AsyncMock(return_value=FAKE_CALL_ROW))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/calls/call-uuid-1")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "call-uuid-1"
    assert body["agent"] == {"id": "agent-uuid-1", "name": "Jane Smith"}
    assert body["transcript"]["redacted_text"] == "Hello [REDACTED], calling about your account."
    assert body["outcome"]["disposition"] == "callback"


@pytest.mark.asyncio
async def test_get_call_audit_returns_events(auth, monkeypatch):
    monkeypatch.setattr(
        "app.api.calls.storage.get_call_audit",
        AsyncMock(return_value=[FAKE_AUDIT_ROW]),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/calls/call-uuid-1/audit")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["event"] == "transcription_completed"
