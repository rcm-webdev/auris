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
