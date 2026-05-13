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
