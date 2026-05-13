import json
import uuid
import pytest
from app.services import storage
from app.config import get_settings


TEST_SID = f"CA_test_{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
async def cleanup(db_pool):
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM audit_log WHERE call_id IN (
                SELECT id FROM calls WHERE twilio_call_sid = $1
            )
            """,
            TEST_SID,
        )
        await conn.execute(
            """
            DELETE FROM transcripts WHERE call_id IN (
                SELECT id FROM calls WHERE twilio_call_sid = $1
            )
            """,
            TEST_SID,
        )
        await conn.execute(
            """
            DELETE FROM outcomes WHERE call_id IN (
                SELECT id FROM calls WHERE twilio_call_sid = $1
            )
            """,
            TEST_SID,
        )
        await conn.execute(
            "DELETE FROM calls WHERE twilio_call_sid = $1", TEST_SID
        )


@pytest.mark.asyncio
async def test_upsert_call_creates_row(db_pool):
    call_id = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 90, None, None
    )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM calls WHERE id = $1::UUID", call_id
        )
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_upsert_call_is_idempotent(db_pool):
    id1 = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 90, None, None
    )
    id2 = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec2", 120, None, None
    )
    assert id1 == id2


@pytest.mark.asyncio
async def test_update_call_status(db_pool):
    call_id = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 0, None, None
    )
    await storage.update_call_status(db_pool, call_id, "transcribed")
    async with db_pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM calls WHERE id = $1::UUID", call_id
        )
    assert status == "transcribed"


@pytest.mark.asyncio
async def test_save_transcript_stores_encrypted(db_pool):
    call_id = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 0, None, None
    )
    await storage.save_transcript(db_pool, call_id, "Hello [REDACTED]", "whisper-1")
    async with db_pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT redacted_text::TEXT FROM transcripts WHERE call_id = $1::UUID",
            call_id,
        )
        decrypted = await conn.fetchval(
            "SELECT pgp_sym_decrypt(redacted_text::bytea, $1) FROM transcripts WHERE call_id = $2::UUID",
            get_settings().encryption_key, call_id,
        )
    assert "Hello" not in raw  # stored as ciphertext
    assert decrypted == "Hello [REDACTED]"


@pytest.mark.asyncio
async def test_save_outcome(db_pool):
    call_id = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 0, None, None
    )
    outcome = {"summary": "Good call", "disposition": "callback", "next_action": "Follow up"}
    await storage.save_outcome(db_pool, call_id, outcome)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT summary, disposition, next_action FROM outcomes WHERE call_id = $1::UUID",
            call_id,
        )
    assert row["summary"] == "Good call"
    assert row["disposition"] == "callback"
    assert row["next_action"] == "Follow up"


@pytest.mark.asyncio
async def test_append_audit(db_pool):
    call_id = await storage.upsert_call(
        db_pool, TEST_SID, "https://example.com/rec", 0, None, None
    )
    await storage.append_audit(db_pool, call_id, "test_event", {"key": "val"})
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT event, metadata FROM audit_log WHERE call_id = $1::UUID ORDER BY created_at DESC LIMIT 1",
            call_id,
        )
    assert row["event"] == "test_event"
    assert json.loads(row["metadata"]) == {"key": "val"}
