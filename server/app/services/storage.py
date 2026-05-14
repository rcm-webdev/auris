import json as _json

import asyncpg

from app.config import get_settings


async def upsert_call(
    pool: asyncpg.Pool,
    call_sid: str,
    recording_url: str,
    duration_seconds: int,
    called_at: str | None,
    agent_id: str | None,
) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO calls (twilio_call_sid, recording_url, duration_seconds, called_at, agent_id, status)
            VALUES ($1, $2, $3, $4::TIMESTAMPTZ, $5::UUID, 'pending')
            ON CONFLICT (twilio_call_sid) DO UPDATE
                SET recording_url     = EXCLUDED.recording_url,
                    duration_seconds  = EXCLUDED.duration_seconds
            RETURNING id::TEXT
            """,
            call_sid,
            recording_url,
            duration_seconds,
            called_at,
            agent_id,
        )
    return row["id"]


async def update_call_status(pool: asyncpg.Pool, call_id: str, status: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE calls SET status = $1 WHERE id = $2::UUID",
            status,
            call_id,
        )


async def save_transcript(
    pool: asyncpg.Pool,
    call_id: str,
    redacted_text: str,
    whisper_model: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO transcripts (call_id, redacted_text, whisper_model, created_at)
            VALUES ($1::UUID, pgp_sym_encrypt($2, $3), $4, NOW())
            ON CONFLICT (call_id) DO UPDATE
                SET redacted_text = EXCLUDED.redacted_text,
                    whisper_model = EXCLUDED.whisper_model
            """,
            call_id,
            redacted_text,
            get_settings().encryption_key,
            whisper_model,
        )


async def save_outcome(pool: asyncpg.Pool, call_id: str, outcome: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO outcomes (call_id, summary, disposition, next_action, raw_json, created_at)
            VALUES ($1::UUID, $2, $3, $4, $5::JSONB, NOW())
            ON CONFLICT (call_id) DO UPDATE
                SET summary     = EXCLUDED.summary,
                    disposition = EXCLUDED.disposition,
                    next_action = EXCLUDED.next_action,
                    raw_json    = EXCLUDED.raw_json
            """,
            call_id,
            outcome.get("summary"),
            outcome.get("disposition"),
            outcome.get("next_action"),
            _json.dumps(outcome),
        )


async def append_audit(
    pool: asyncpg.Pool,
    call_id: str,
    event: str,
    metadata: dict | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log (call_id, event, actor, metadata, created_at)
            VALUES ($1::UUID, $2, 'system', $3::JSONB, NOW())
            """,
            call_id,
            event,
            _json.dumps(metadata) if metadata else None,
        )


async def list_calls(
    pool: asyncpg.Pool,
    agent_id: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    conditions: list[str] = []
    params: list = []
    idx = 1

    if agent_id:
        conditions.append(f"c.agent_id = ${idx}::UUID")
        params.append(agent_id)
        idx += 1
    if status:
        conditions.append(f"c.status = ${idx}")
        params.append(status)
        idx += 1
    if from_date:
        conditions.append(f"c.called_at >= ${idx}::TIMESTAMPTZ")
        params.append(from_date)
        idx += 1
    if to_date:
        conditions.append(f"c.called_at <= ${idx}::TIMESTAMPTZ")
        params.append(to_date)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * limit

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM calls c {where}", *params)
        rows = await conn.fetch(
            f"""
            SELECT c.id::TEXT, c.twilio_call_sid, c.duration_seconds, c.called_at, c.status,
                   a.id::TEXT AS agent_id, a.name AS agent_name
            FROM calls c LEFT JOIN agents a ON a.id = c.agent_id
            {where}
            ORDER BY c.called_at DESC NULLS LAST
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )
    return [dict(r) for r in rows], total


async def get_call(pool: asyncpg.Pool, call_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT c.id::TEXT, c.twilio_call_sid, c.recording_url,
                   c.duration_seconds, c.called_at, c.status,
                   a.id::TEXT AS agent_id, a.name AS agent_name,
                   pgp_sym_decrypt(t.redacted_text::bytea, $2) AS redacted_text,
                   t.whisper_model,
                   o.summary, o.disposition, o.next_action
            FROM calls c
            LEFT JOIN agents a ON a.id = c.agent_id
            LEFT JOIN transcripts t ON t.call_id = c.id
            LEFT JOIN outcomes o ON o.call_id = c.id
            WHERE c.id = $1::UUID
            """,
            call_id,
            get_settings().encryption_key,
        )
    return dict(row) if row else None


async def get_call_audit(pool: asyncpg.Pool, call_id: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::TEXT, event, actor, metadata, created_at
            FROM audit_log WHERE call_id = $1::UUID ORDER BY created_at ASC
            """,
            call_id,
        )
    return [dict(r) for r in rows]


async def list_agents(pool: asyncpg.Pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id::TEXT, a.name, a.email, a.created_at,
                   COUNT(c.id) AS total_calls,
                   COUNT(c.id) FILTER (WHERE c.status = 'extracted') AS completed_calls
            FROM agents a LEFT JOIN calls c ON c.agent_id = a.id
            GROUP BY a.id ORDER BY a.name ASC
            """,
        )
    return [dict(r) for r in rows]


async def create_agent(pool: asyncpg.Pool, name: str, email: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agents (name, email)
            VALUES ($1, $2)
            RETURNING id::TEXT, name, email, created_at
            """,
            name,
            email,
        )
    return {**dict(row), "total_calls": 0, "completed_calls": 0}


async def get_agent(pool: asyncpg.Pool, agent_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT a.id::TEXT, a.name, a.email, a.created_at,
                   COUNT(c.id) AS total_calls,
                   COUNT(c.id) FILTER (WHERE c.status = 'extracted') AS completed_calls
            FROM agents a LEFT JOIN calls c ON c.agent_id = a.id
            WHERE a.id = $1::UUID
            GROUP BY a.id
            """,
            agent_id,
        )
    return dict(row) if row else None
