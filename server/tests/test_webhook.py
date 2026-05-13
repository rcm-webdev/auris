import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app

VALID_FORM = {
    "CallSid": "CA_webhook_test_001",
    "RecordingUrl": "https://api.twilio.com/Recordings/RE123",
    "RecordingDuration": "60",
    "RecordingStatus": "completed",
}


@pytest.fixture
def mock_pipeline(monkeypatch):
    async def fake_pipeline(*args, **kwargs):
        pass
    monkeypatch.setattr("app.api.webhooks.run_pipeline", fake_pipeline)


@pytest.fixture
def mock_storage_upsert(monkeypatch):
    monkeypatch.setattr(
        "app.api.webhooks.storage.upsert_call",
        AsyncMock(return_value="00000000-0000-0000-0000-000000000001"),
    )
    # Provide a dummy pool so request.app.state.pool doesn't raise
    app.state.pool = MagicMock()


@pytest.mark.asyncio
async def test_valid_signature_returns_200(mock_pipeline, mock_storage_upsert):
    with patch("app.api.webhooks.RequestValidator") as mock_val_cls:
        mock_val = MagicMock()
        mock_val.validate.return_value = True
        mock_val_cls.return_value = mock_val

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/webhooks/recording",
                data=VALID_FORM,
                headers={"X-Twilio-Signature": "valid-sig"},
            )

    assert response.status_code == 200
    assert response.json()["received"] is True


@pytest.mark.asyncio
async def test_invalid_signature_returns_403():
    with patch("app.api.webhooks.RequestValidator") as mock_val_cls:
        mock_val = MagicMock()
        mock_val.validate.return_value = False
        mock_val_cls.return_value = mock_val

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/webhooks/recording",
                data=VALID_FORM,
                headers={"X-Twilio-Signature": "bad-sig"},
            )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_missing_required_field_returns_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/webhooks/recording",
            data={"CallSid": "CA123"},  # missing RecordingUrl
        )
    assert response.status_code == 422
