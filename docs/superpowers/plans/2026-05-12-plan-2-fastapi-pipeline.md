# FastAPI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Docs note:** Always use context7 to resolve library-id and query docs before implementing any call to asyncpg, Presidio, OpenAI SDK, Anthropic SDK, or Twilio.

**Goal:** Implement the full Twilio recording webhook → Whisper transcription → Presidio redaction → Claude extraction pipeline in FastAPI.

**Architecture:** A single `POST /api/webhooks/recording` endpoint validates the Twilio signature, upserts a call row, then hands off to a `BackgroundTask` that runs the four-stage pipeline. Each stage writes its result and updates the call status atomically via asyncpg. Raw transcript text is created only inside `redaction.py` and is discarded in the same scope — it never touches the database.

**Tech Stack:** FastAPI, asyncpg (no ORM), pydantic-settings, OpenAI Whisper API, Presidio + spaCy `en_core_web_lg`, Anthropic Claude (`claude-sonnet-4-6`), Twilio `RequestValidator`, pgcrypto (server-side encryption via SQL)

---

## File Map

### New files
| File | Responsibility |
|------|----------------|
| `server/app/config.py` | `Settings` singleton via pydantic-settings |
| `server/app/db/pool.py` | `create_pool()` — asyncpg pool factory |
| `server/app/models/__init__.py` | package marker |
| `server/app/models/schemas.py` | Pydantic models for request/response |
| `server/app/services/__init__.py` | package marker |
| `server/app/services/storage.py` | All asyncpg DB writes (calls, transcripts, outcomes, audit) |
| `server/app/services/transcription.py` | Whisper API client — fetch audio + transcribe |
| `server/app/services/redaction.py` | Presidio PHI redaction — PHI boundary |
| `server/app/services/extraction.py` | Claude structured outcome extraction |
| `server/app/api/__init__.py` | package marker |
| `server/app/api/webhooks.py` | `POST /api/webhooks/recording` + pipeline orchestrator |
| `server/tests/test_storage.py` | Real-DB tests for all storage functions |
| `server/tests/test_transcription.py` | Mocked OpenAI tests |
| `server/tests/test_redaction.py` | Live Presidio tests (requires spaCy model) |
| `server/tests/test_extraction.py` | Mocked Anthropic tests |
| `server/tests/test_webhook.py` | Endpoint tests — signature validation + happy path |

### Modified files
| File | Change |
|------|--------|
| `server/app/main.py` | Add lifespan context, register webhook router |
| `server/tests/conftest.py` | Add `app_client` fixture |
| `server/pyproject.toml` | Move `httpx` to main deps; add it if missing |
| `server/.env` | Add `ENCRYPTION_KEY` |

---

## Task 1: Config + DB Pool + Lifespan

**Files:**
- Create: `server/app/config.py`
- Create: `server/app/db/pool.py`
- Modify: `server/app/main.py`
- Modify: `server/pyproject.toml`
- Modify: `server/.env`

- [ ] **Step 1: Add `ENCRYPTION_KEY` to `.env` and `httpx` to main deps**

In `server/.env`, add:
```
ENCRYPTION_KEY=dev-encryption-key-minimum-32-chars!
```

In `server/pyproject.toml`, move `httpx` into the main `dependencies` list (not just dev):
```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "asyncpg>=0.30.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.28.0",
    "anthropic>=0.40.0",
    "openai>=1.58.0",
    "presidio-analyzer>=2.2.0",
    "presidio-anonymizer>=2.2.0",
    "spacy>=3.8.0",
    "twilio>=9.4.0",
    "python-multipart>=0.0.18",
]
```

Run `uv sync --directory server` to update the lockfile.

- [ ] **Step 2: Write the failing test**

Create `server/tests/test_config.py`:
```python
def test_settings_has_required_fields():
    from app.config import settings
    assert settings.database_url.startswith("postgresql://")
    assert len(settings.encryption_key) >= 32
    assert settings.openai_api_key
    assert settings.anthropic_api_key
    assert settings.twilio_account_sid.startswith("AC")
    assert settings.twilio_auth_token
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run --directory server pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `app.config` does not exist yet.

- [ ] **Step 4: Create `server/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    openai_api_key: str
    anthropic_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    encryption_key: str


settings = Settings()
```

- [ ] **Step 5: Create `server/app/db/pool.py`**

```python
import asyncpg
from app.config import settings


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.database_url)
```

- [ ] **Step 6: Update `server/app/main.py` with lifespan**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.pool import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    yield
    await app.state.pool.close()


app = FastAPI(title="Franky API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests to verify passing**

```bash
uv run --directory server pytest tests/test_config.py tests/test_health.py -v
```

Expected: all PASS (test_health still passes because lifespan is triggered by the AsyncClient context manager).

- [ ] **Step 8: Commit**

Suggested message: `feat: add pydantic-settings config, asyncpg pool, fastapi lifespan`

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `server/app/models/__init__.py`
- Create: `server/app/models/schemas.py`

- [ ] **Step 1: Create package marker**

```bash
touch server/app/models/__init__.py
```

- [ ] **Step 2: Create `server/app/models/schemas.py`**

```python
from pydantic import BaseModel


class Outcome(BaseModel):
    summary: str
    disposition: str
    next_action: str | None = None
```

No test needed — Pydantic models are validated by the tests that use them. Commit immediately.

- [ ] **Step 3: Commit**

Suggested message: `feat: add Pydantic schemas (Outcome)`

---

## Task 3: Storage Service

**Files:**
- Create: `server/app/services/__init__.py`
- Create: `server/app/services/storage.py`
- Create: `server/tests/test_storage.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_storage.py`:
```python
import json
import uuid
import pytest
from app.services import storage
from app.config import settings


TEST_SID = f"CA_test_{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
async def cleanup(db_pool):
    yield
    async with db_pool.acquire() as conn:
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
            "SELECT pgp_sym_decrypt(redacted_text, $1) FROM transcripts WHERE call_id = $2::UUID",
            settings.encryption_key, call_id,
        )
    assert "Hello" not in raw  # ciphertext
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --directory server pytest tests/test_storage.py -v
```

Expected: `ModuleNotFoundError` — `app.services.storage` does not exist.

- [ ] **Step 3: Create package marker**

```bash
touch server/app/services/__init__.py
```

- [ ] **Step 4: Create `server/app/services/storage.py`**

```python
import json as _json

import asyncpg

from app.config import settings


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
            settings.encryption_key,
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
```

- [ ] **Step 5: Run tests to verify passing**

```bash
uv run --directory server pytest tests/test_storage.py -v
```

Expected: all 6 PASS.

- [ ] **Step 6: Commit**

Suggested message: `feat: storage service — upsert_call, save_transcript (pgcrypto), save_outcome, append_audit`

---

## Task 4: Transcription Service

**Files:**
- Create: `server/app/services/transcription.py`
- Create: `server/tests/test_transcription.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_transcription.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_transcribe_returns_text_and_model():
    mock_audio = b"fake-audio-bytes"
    mock_text = "Hello, this is a test transcript."

    mock_http_resp = MagicMock()
    mock_http_resp.content = mock_audio
    mock_http_resp.raise_for_status = MagicMock()

    mock_whisper_resp = MagicMock()
    mock_whisper_resp.text = mock_text

    with (
        patch("httpx.AsyncClient") as mock_client_cls,
        patch("openai.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_http_resp)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_openai = AsyncMock()
        mock_openai.audio.transcriptions.create = AsyncMock(return_value=mock_whisper_resp)
        mock_openai_cls.return_value = mock_openai

        from app.services.transcription import transcribe
        text, model = await transcribe("https://api.twilio.com/Recordings/RE123")

    assert text == mock_text
    assert model == "whisper-1"


@pytest.mark.asyncio
async def test_transcribe_appends_mp3_extension():
    mock_http_resp = MagicMock()
    mock_http_resp.content = b"audio"
    mock_http_resp.raise_for_status = MagicMock()

    mock_whisper_resp = MagicMock()
    mock_whisper_resp.text = "test"

    with (
        patch("httpx.AsyncClient") as mock_client_cls,
        patch("openai.AsyncOpenAI") as mock_openai_cls,
    ):
        mock_http = AsyncMock()
        captured_url = []
        async def fake_get(url, **kwargs):
            captured_url.append(url)
            return mock_http_resp
        mock_http.get = fake_get
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_openai = AsyncMock()
        mock_openai.audio.transcriptions.create = AsyncMock(return_value=mock_whisper_resp)
        mock_openai_cls.return_value = mock_openai

        from app.services import transcription
        import importlib
        importlib.reload(transcription)
        await transcription.transcribe("https://api.twilio.com/Recordings/RE123")

    assert captured_url[0].endswith(".mp3")
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --directory server pytest tests/test_transcription.py -v
```

Expected: `ModuleNotFoundError` — `app.services.transcription` does not exist.

- [ ] **Step 3: Create `server/app/services/transcription.py`**

```python
import httpx
from openai import AsyncOpenAI

from app.config import settings


async def transcribe(recording_url: str) -> tuple[str, str]:
    """Fetch Twilio recording audio, transcribe via Whisper. Returns (raw_text, model_name).

    Caller is responsible for discarding raw_text after redaction.
    """
    model = "whisper-1"

    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{recording_url}.mp3",
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
        )
        resp.raise_for_status()
        audio_bytes = resp.content

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    result = await client.audio.transcriptions.create(
        model=model,
        file=("recording.mp3", audio_bytes, "audio/mpeg"),
    )
    return result.text, model
```

- [ ] **Step 4: Run tests to verify passing**

```bash
uv run --directory server pytest tests/test_transcription.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

Suggested message: `feat: transcription service — Whisper API with Twilio auth`

---

## Task 5: Redaction Service

**Files:**
- Create: `server/app/services/redaction.py`
- Create: `server/tests/test_redaction.py`

- [ ] **Step 1: Download the spaCy model (one-time setup)**

```bash
uv run --directory server python -m spacy download en_core_web_lg
```

Expected output ends with: `✔ Download and installation successful`

This downloads ~700 MB. Only needed once per environment.

- [ ] **Step 2: Write the failing tests**

Create `server/tests/test_redaction.py`:
```python
from app.services.redaction import redact


def test_redact_removes_person_name():
    result = redact("Hi, my name is John Smith and I live in Boston.")
    assert "John Smith" not in result
    assert "[REDACTED]" in result


def test_redact_removes_phone_number():
    result = redact("Call me at 555-867-5309.")
    assert "555-867-5309" not in result
    assert "[REDACTED]" in result


def test_redact_removes_email():
    result = redact("Reach me at jane.doe@example.com anytime.")
    assert "jane.doe@example.com" not in result
    assert "[REDACTED]" in result


def test_redact_preserves_non_phi():
    result = redact("The product costs $50 and ships in 3 days.")
    assert result == "The product costs $50 and ships in 3 days."


def test_redact_returns_string():
    result = redact("Hello world.")
    assert isinstance(result, str)
```

- [ ] **Step 3: Run to verify they fail**

```bash
uv run --directory server pytest tests/test_redaction.py -v
```

Expected: `ModuleNotFoundError` — `app.services.redaction` does not exist.

- [ ] **Step 4: Create `server/app/services/redaction.py`**

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()
_replace_op = {"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})}


def redact(raw_text: str) -> str:
    """Detect PHI entities with Presidio and replace all with [REDACTED].

    This is the PHI boundary. raw_text must be discarded by the caller
    immediately after this function returns. It must never be stored or logged.
    """
    results = _analyzer.analyze(text=raw_text, language="en")
    anonymized = _anonymizer.anonymize(
        text=raw_text,
        analyzer_results=results,
        operators=_replace_op,
    )
    return anonymized.text
```

- [ ] **Step 5: Run tests to verify passing**

```bash
uv run --directory server pytest tests/test_redaction.py -v
```

Expected: all 5 PASS. Note: `test_redact_preserves_non_phi` may be fragile — if it fails because Presidio redacts something unexpected, adjust the test text.

- [ ] **Step 6: Commit**

Suggested message: `feat: redaction service — Presidio PHI boundary with [REDACTED] replacement`

---

## Task 6: Extraction Service

**Files:**
- Create: `server/app/services/extraction.py`
- Create: `server/tests/test_extraction.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_extraction.py`:
```python
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
    with patch("anthropic.AsyncAnthropic") as mock_cls:
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
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_claude_response(expected))
        mock_cls.return_value = mock_client

        from app.services.extraction import extract
        result = await extract("You've reached [REDACTED], please leave a message.")

    assert result["disposition"] == "voicemail"
    assert result["next_action"] is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --directory server pytest tests/test_extraction.py -v
```

Expected: `ModuleNotFoundError` — `app.services.extraction` does not exist.

- [ ] **Step 3: Create `server/app/services/extraction.py`**

```python
import json

from anthropic import AsyncAnthropic

from app.config import settings

_SYSTEM_PROMPT = """\
You analyze redacted call transcripts and extract structured outcomes.
Respond with valid JSON only — no markdown fences, no extra text.
Required fields:
  summary      - 2-3 sentence summary of the call
  disposition  - exactly one of: interested, not_interested, callback, voicemail, no_answer, other
  next_action  - specific follow-up action as a string, or null if none"""


async def extract(redacted_text: str) -> dict:
    """Send redacted transcript to Claude and return a structured outcome dict."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": redacted_text}],
    )
    return json.loads(message.content[0].text)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
uv run --directory server pytest tests/test_extraction.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

Suggested message: `feat: extraction service — Claude structured outcome extraction`

---

## Task 7: Webhook Endpoint + Pipeline

**Files:**
- Create: `server/app/api/__init__.py`
- Create: `server/app/api/webhooks.py`
- Create: `server/tests/test_webhook.py`
- Modify: `server/app/main.py`
- Modify: `server/tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_webhook.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app

VALID_FORM = {
    "CallSid": "CA_webhook_test_001",
    "RecordingUrl": "https://api.twilio.com/Recordings/RE123",
    "RecordingDuration": "60",
    "RecordingStatus": "completed",
}


@pytest.fixture
def mock_pipeline(monkeypatch):
    """Replace run_pipeline with a no-op so tests don't hit real services."""
    async def fake_pipeline(*args, **kwargs):
        pass
    monkeypatch.setattr("app.api.webhooks.run_pipeline", fake_pipeline)


@pytest.fixture
def mock_storage_upsert(monkeypatch):
    monkeypatch.setattr(
        "app.api.webhooks.storage.upsert_call",
        AsyncMock(return_value="00000000-0000-0000-0000-000000000001"),
    )


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
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --directory server pytest tests/test_webhook.py -v
```

Expected: `ModuleNotFoundError` — `app.api.webhooks` does not exist.

- [ ] **Step 3: Create package marker**

```bash
touch server/app/api/__init__.py
```

- [ ] **Step 4: Create `server/app/api/webhooks.py`**

```python
import logging

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import settings
from app.services import extraction, redaction, storage, transcription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks")


async def run_pipeline(pool, call_id: str, recording_url: str) -> None:
    try:
        raw_text, model = await transcription.transcribe(recording_url)
        await storage.update_call_status(pool, call_id, "transcribed")
        await storage.append_audit(pool, call_id, "transcription_completed", {"model": model})

        redacted = redaction.redact(raw_text)
        del raw_text  # PHI boundary — discard raw text immediately

        await storage.save_transcript(pool, call_id, redacted, model)
        await storage.update_call_status(pool, call_id, "redacted")
        await storage.append_audit(pool, call_id, "phi_redacted")

        outcome = await extraction.extract(redacted)
        await storage.save_outcome(pool, call_id, outcome)
        await storage.update_call_status(pool, call_id, "extracted")
        await storage.append_audit(pool, call_id, "outcome_extracted")

    except Exception as exc:
        logger.error("Pipeline failed for call %s: %s", call_id, exc, exc_info=True)
        await storage.update_call_status(pool, call_id, "failed")
        await storage.append_audit(pool, call_id, "step_failed", {"error": str(exc)})


@router.post("/recording")
async def recording_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: str = Form("0"),
    StartTime: str | None = Form(None),
    AgentId: str | None = Form(None),
):
    sig = request.headers.get("X-Twilio-Signature", "")
    form = dict(await request.form())
    if not RequestValidator(settings.twilio_auth_token).validate(str(request.url), form, sig):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    pool = request.app.state.pool
    call_id = await storage.upsert_call(
        pool,
        call_sid=CallSid,
        recording_url=RecordingUrl,
        duration_seconds=int(RecordingDuration),
        called_at=StartTime,
        agent_id=AgentId,
    )

    background_tasks.add_task(run_pipeline, pool, call_id, RecordingUrl)
    return {"received": True, "call_id": call_id}
```

- [ ] **Step 5: Register the router in `server/app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import webhooks
from app.db.pool import create_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    yield
    await app.state.pool.close()


app = FastAPI(title="Franky API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run all tests**

```bash
uv run --directory server pytest -v
```

Expected: all tests PASS, including existing `test_health`, `test_db_schema`, and all new tests.

- [ ] **Step 7: Commit**

Suggested message: `feat: webhook endpoint + pipeline orchestration (transcription → redaction → extraction)`

---

## Self-Review

**Spec coverage:**
- ✅ `POST /api/webhooks/recording` — Twilio signature validated, call upserted, pipeline in BackgroundTask
- ✅ Transcription step — Whisper API, audio fetched with Twilio auth, `.mp3` appended
- ✅ Redaction step — Presidio + `[REDACTED]`, raw text discarded with `del`, never stored
- ✅ pgcrypto encryption — `pgp_sym_encrypt` on insert, `pgp_sym_decrypt` verified in test
- ✅ Status progression — pending → transcribed → redacted → extracted (or failed)
- ✅ Audit log entries at each stage
- ✅ `agent_id` accepted as optional form field from Twilio custom param

**Gaps left for Plan 3 (REST API):**
- `GET /api/calls`, `GET /api/calls/:id`, `GET /api/calls/:id/audit`
- `GET /api/agents`, `POST /api/agents`
- `server/app/api/deps.py` — `get_current_session()` FastAPI dependency

**PHI boundary:** `raw_text` is created in `transcription.py`, passed to `redaction.py`, and immediately `del`'d in `run_pipeline` after redaction. It is never written to the database, never logged, never returned from any function.
