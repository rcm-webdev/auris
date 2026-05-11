import asyncpg
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/franky_dev")


@pytest.fixture(scope="session")
async def db_pool():
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
    except Exception as exc:
        pytest.fail(f"Could not connect to database at {DATABASE_URL}: {exc}")
    yield pool
    await pool.close()
