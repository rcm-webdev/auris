from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_session
from app.main import app

FAKE_USER = {"id": "user1", "name": "Test User", "email": "test@example.com"}

FAKE_AGENT = {
    "id": "agent-uuid-1",
    "name": "Jane Smith",
    "email": "jane@example.com",
    "created_at": datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
    "total_calls": 5,
    "completed_calls": 3,
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
async def test_list_agents_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agents")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_agents_returns_shape(auth, monkeypatch):
    monkeypatch.setattr("app.api.agents.storage.list_agents", AsyncMock(return_value=[FAKE_AGENT]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agents")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"][0]["name"] == "Jane Smith"


@pytest.mark.asyncio
async def test_create_agent_returns_201(auth, monkeypatch):
    new_agent = {
        "id": "agent-uuid-new",
        "name": "Bob Jones",
        "email": "bob@example.com",
        "created_at": datetime(2026, 5, 13, 9, 0, 0, tzinfo=timezone.utc),
        "total_calls": 0,
        "completed_calls": 0,
    }
    monkeypatch.setattr("app.api.agents.storage.create_agent", AsyncMock(return_value=new_agent))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agents", json={"name": "Bob Jones", "email": "bob@example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "agent-uuid-new"
    assert body["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_create_agent_duplicate_email_returns_409(auth, monkeypatch):
    monkeypatch.setattr(
        "app.api.agents.storage.create_agent",
        AsyncMock(side_effect=asyncpg.UniqueViolationError()),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agents", json={"name": "Dupe", "email": "dupe@example.com"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_agent_not_found(auth, monkeypatch):
    monkeypatch.setattr("app.api.agents.storage.get_agent", AsyncMock(return_value=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agents/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_returns_stats(auth, monkeypatch):
    monkeypatch.setattr("app.api.agents.storage.get_agent", AsyncMock(return_value=FAKE_AGENT))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agents/agent-uuid-1")
    assert response.status_code == 200
    body = response.json()
    assert body["total_calls"] == 5
    assert body["completed_calls"] == 3
