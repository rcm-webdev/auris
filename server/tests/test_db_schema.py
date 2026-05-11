import pytest

EXPECTED_TABLES = {"agents", "calls", "transcripts", "outcomes", "audit_log"}


@pytest.mark.asyncio
async def test_all_tables_exist(db_pool):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
    found = {r["tablename"] for r in rows}
    assert EXPECTED_TABLES.issubset(found), (
        f"Missing tables: {EXPECTED_TABLES - found}"
    )


@pytest.mark.asyncio
async def test_transcripts_phi_constraints(db_pool):
    async with db_pool.acquire() as conn:
        redacted_text_col = await conn.fetchrow(
            """SELECT is_nullable FROM information_schema.columns
               WHERE table_name = 'transcripts' AND column_name = 'redacted_text'"""
        )
        call_id_unique = await conn.fetchrow(
            """SELECT COUNT(*) as cnt FROM information_schema.table_constraints tc
               JOIN information_schema.constraint_column_usage ccu
                 ON tc.constraint_name = ccu.constraint_name
               WHERE tc.table_name = 'transcripts'
                 AND tc.constraint_type = 'UNIQUE'
                 AND ccu.column_name = 'call_id'"""
        )
    assert redacted_text_col["is_nullable"] == "NO", (
        "transcripts.redacted_text must be NOT NULL — PHI boundary requires content"
    )
    assert call_id_unique["cnt"] >= 1, (
        "transcripts.call_id must have a UNIQUE constraint — one transcript per call"
    )


@pytest.mark.asyncio
async def test_calls_status_constraint(db_pool):
    import asyncpg
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO agents (name, email) VALUES ('Test Agent', 'test@example.com')"
        )
        agent_id = await conn.fetchval("SELECT id FROM agents WHERE email = 'test@example.com'")
        try:
            await conn.execute(
                """INSERT INTO calls (agent_id, twilio_call_sid, status)
                   VALUES ($1, 'CA_test_invalid', 'invalid_status')""",
                agent_id,
            )
            assert False, "Should have raised a CheckViolationError for invalid status"
        except asyncpg.exceptions.CheckViolationError:
            pass  # Expected — constraint is working
        finally:
            await conn.execute("DELETE FROM agents WHERE email = 'test@example.com'")
