# Voice Call Logger — Plan 1: Monorepo Scaffold + Database

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the monorepo skeleton — root npm workspace, React Router v7 client shell, FastAPI server with a passing health-check test, and a local Postgres database with the full schema applied and verified.

**Architecture:** npm workspaces manage the client; Python `uv` manages the server. Both share a single local Postgres database via `DATABASE_URL`. No business logic in this plan — just the scaffolding every other plan builds on.

**Tech Stack:** Node 20+, npm workspaces, concurrently, React Router v7 (SPA mode), FastAPI 0.115+, asyncpg, PostgreSQL, `uv` (Python package manager)

---

## File Map

| Path | Responsibility |
|------|---------------|
| `package.json` | Root — workspaces config, concurrently dev scripts |
| `.gitignore` | Ignores node_modules, .venv, .env, __pycache__ |
| `client/` | React Router v7 workspace (scaffolded by CLI) |
| `client/react-router.config.ts` | SPA mode (`ssr: false`) |
| `client/.env.example` | `VITE_API_URL` |
| `server/pyproject.toml` | Python project + all runtime and dev dependencies |
| `server/.env.example` | All env vars documented (including keys used in later plans) |
| `server/app/__init__.py` | Empty package marker |
| `server/app/main.py` | FastAPI app, CORS middleware, `/health` route |
| `server/app/db/__init__.py` | Empty package marker |
| `server/app/db/migrations/001_initial.sql` | Full schema: agents, calls, transcripts, outcomes, audit_log |
| `server/tests/__init__.py` | Empty package marker |
| `server/tests/conftest.py` | Session-scoped asyncpg pool fixture |
| `server/tests/test_health.py` | GET /health → 200 `{"status":"ok"}` |
| `server/tests/test_db_schema.py` | Verifies all 5 tables exist in public schema |

---

### Task 1: Git init + root workspace

**Files:**
- Create: `package.json`
- Create: `package-lock.json` (auto-generated)

- [ ] **Step 1: Initialize git**

```bash
cd /Users/aokiji/Developer/franky
git init
```

Expected:
```
Initialized empty Git repository in /Users/aokiji/Developer/franky/.git/
```

- [ ] **Step 2: Write root `package.json`**

Create `/Users/aokiji/Developer/franky/package.json`:

```json
{
  "name": "franky",
  "private": true,
  "workspaces": [
    "client"
  ],
  "scripts": {
    "dev": "concurrently -n client,server -c cyan,yellow \"npm run dev -w client\" \"uv run --directory server uvicorn app.main:app --reload --port 8000\"",
    "dev:client": "npm run dev -w client",
    "dev:server": "uv run --directory server uvicorn app.main:app --reload --port 8000"
  },
  "devDependencies": {
    "concurrently": "^9.1.0"
  }
}
```

- [ ] **Step 3: Install root dependencies**

```bash
npm install
```

Expected: `node_modules/` created, `package-lock.json` written, `concurrently` installed.

- [ ] **Step 4: Notify user — ready to commit**

Tell the user:
> Ready to commit Task 1. Suggested message:
> ```
> git add package.json package-lock.json
> git commit -m "chore: root npm workspace with concurrently dev scripts"
> ```

---

### Task 2: .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Write `.gitignore`**

Create `/Users/aokiji/Developer/franky/.gitignore`:

```
# Node
node_modules/
npm-debug.log*
*.tsbuildinfo

# Build output
dist/
dist-ssr/
build/
coverage/

# Vite
.vite/

# Env files (.env.example files ARE committed)
.env
.env.*
!.env.example

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.so
.venv/
.pytest_cache/
*.egg-info/
.ruff_cache/
.coverage
htmlcov/
*.log

# pyenv
.python-version

# OS
.DS_Store
Thumbs.db

# Editor
.idea/
.vscode/
*.swp
*.orig

# Security artifacts — never commit
*.pem
*.key

# Temp
tmp/
.tmp/
```

- [ ] **Step 2: Verify key patterns work correctly**

```bash
git check-ignore -v server/.env          # must be ignored
git check-ignore -v server/.env.example  # must NOT be ignored (prints nothing)
git check-ignore -v client/dist/         # must be ignored
git check-ignore -v .DS_Store            # must be ignored
```

- [ ] **Step 3: Notify user — ready to commit**

Tell the user:
> Ready to commit Task 2. Suggested message:
> ```
> git add .gitignore
> git commit -m "chore: gitignore for Node, Python, and OS artifacts"
> ```

---

### Task 3: Client workspace (React Router v7, SPA mode)

**Files:**
- Create: `client/` (scaffolded by CLI)
- Modify: `client/react-router.config.ts`
- Create: `client/.env.example`

Prerequisites: Node 20+ and npm installed.

- [ ] **Step 1: Scaffold with create-react-router**

```bash
npx create-react-router@latest client --package-manager npm
```

When prompted interactively:
- **Initialize a new git repository?** → **No** (root git already exists)
- **Install dependencies with npm?** → **Yes**

Expected: `client/` created with React Router v7 app files, `npm install` runs inside it.

- [ ] **Step 2: Re-run root install to wire up the workspace**

```bash
npm install
```

Expected: no errors; root `node_modules/` updated with workspace symlink.

- [ ] **Step 3: Verify client starts**

```bash
npm run dev:client
```

Open `http://localhost:5173` — the React Router v7 welcome page should appear. Then `Ctrl+C`.

- [ ] **Step 4: Set SPA mode in `client/react-router.config.ts`**

Replace the scaffolded file's entire content with:

```ts
import type { Config } from "@react-router/dev/config";

export default {
  ssr: false,
} satisfies Config;
```

- [ ] **Step 5: Create `client/.env.example`**

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 6: Notify user — ready to commit**

Tell the user:
> Ready to commit Task 3. Suggested message:
> ```
> git add client/ client/.env.example
> git commit -m "feat: scaffold React Router v7 client in SPA mode"
> ```

---

### Task 4: Server workspace (FastAPI + /health, TDD)

**Files:**
- Create: `server/pyproject.toml`
- Create: `server/.env.example`
- Create: `server/app/__init__.py`
- Create: `server/app/main.py`
- Create: `server/tests/__init__.py`
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_health.py`

Prerequisites: Python 3.11+ and `uv` installed.
- Check: `python3 --version` (need 3.11+)
- Install uv if missing: `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_health.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Create `server/pyproject.toml`**

```toml
[project]
name = "franky-server"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "asyncpg>=0.30.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "python-dotenv>=1.0.0",
    "anthropic>=0.40.0",
    "openai>=1.58.0",
    "presidio-analyzer>=2.2.0",
    "presidio-anonymizer>=2.2.0",
    "spacy>=3.8.0",
    "httpx>=0.28.0",
    "twilio>=9.4.0",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "httpx>=0.28.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
testpaths = ["tests"]
```

- [ ] **Step 3: Create package markers + conftest**

Create `server/app/__init__.py` — empty file.

Create `server/tests/__init__.py` — empty file.

Create `server/tests/conftest.py`:

```python
import asyncpg
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/franky_dev")


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(DATABASE_URL)
    yield pool
    await pool.close()
```

- [ ] **Step 4: Install Python dependencies**

```bash
cd server
uv sync --extra dev
```

Expected: `.venv/` created, all packages installed. This will take 1–2 minutes on first run.

```bash
cd ..
```

- [ ] **Step 5: Verify test fails (app not written yet)**

```bash
uv run --directory server pytest tests/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'` — confirms test is correctly wired.

- [ ] **Step 6: Write minimal `server/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Franky API", version="0.1.0")

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

- [ ] **Step 7: Run test — verify it passes**

```bash
uv run --directory server pytest tests/test_health.py -v
```

Expected:
```
tests/test_health.py::test_health_returns_ok PASSED
1 passed in 0.XXs
```

- [ ] **Step 8: Create `server/.env.example`**

```
DATABASE_URL=postgresql://localhost/franky_dev
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WEBHOOK_SECRET=...
```

- [ ] **Step 9: Notify user — ready to commit**

Tell the user:
> Ready to commit Task 4. Suggested message:
> ```
> git add server/
> git commit -m "feat: FastAPI skeleton with /health endpoint and passing test"
> ```

---

### Task 5: Database schema (TDD)

**Files:**
- Create: `server/app/db/__init__.py`
- Create: `server/app/db/migrations/001_initial.sql`
- Create: `server/tests/test_db_schema.py`

Prerequisites: PostgreSQL installed and running locally (`brew install postgresql@16` or similar).
- Check: `psql --version`
- Check server is running: `pg_isready`

- [ ] **Step 1: Create the local database**

```bash
createdb franky_dev
```

Expected: no output (success). If the database already exists: `dropdb franky_dev && createdb franky_dev`.

- [ ] **Step 2: Create `.env` from example**

```bash
cp server/.env.example server/.env
```

`server/.env` already has `DATABASE_URL=postgresql://localhost/franky_dev` — no edits needed. Leave the API key placeholders as-is.

- [ ] **Step 3: Write the failing schema test**

Create `server/tests/test_db_schema.py`:

```python
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
```

- [ ] **Step 4: Run schema test — verify it fails**

```bash
uv run --directory server pytest tests/test_db_schema.py -v
```

Expected: `AssertionError: Missing tables: {'agents', 'calls', 'transcripts', 'outcomes', 'audit_log'}` — confirms tables don't exist yet.

- [ ] **Step 5: Create the migration directories**

```bash
mkdir -p server/app/db/migrations
```

- [ ] **Step 6: Write `server/app/db/__init__.py`**

Empty file — marks `db` as a Python package.

- [ ] **Step 7: Write `server/app/db/migrations/001_initial.sql`**

```sql
-- Enable UUID and encryption support
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Call agents: human reps making outbound calls
CREATE TABLE agents (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  email      TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- One row per recorded call
CREATE TABLE calls (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id         UUID REFERENCES agents(id),
  twilio_call_sid  TEXT UNIQUE NOT NULL,
  recording_url    TEXT,
  duration_seconds INTEGER,
  called_at        TIMESTAMPTZ,
  status           TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'transcribed', 'redacted', 'extracted', 'failed'))
);

-- Redacted transcripts only — raw text is never persisted
CREATE TABLE transcripts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id       UUID UNIQUE REFERENCES calls(id),
  redacted_text TEXT NOT NULL,
  whisper_model TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Claude-extracted structured outcomes
CREATE TABLE outcomes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id     UUID UNIQUE REFERENCES calls(id),
  summary     TEXT,
  disposition TEXT,
  next_action TEXT,
  raw_json    JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Immutable append-only audit trail
CREATE TABLE audit_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id    UUID REFERENCES calls(id),
  event      TEXT NOT NULL,
  actor      TEXT NOT NULL DEFAULT 'system',
  metadata   JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 8: Apply migration**

```bash
psql franky_dev < server/app/db/migrations/001_initial.sql
```

Expected:
```
CREATE EXTENSION
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
CREATE TABLE
```

- [ ] **Step 9: Run schema test — verify it passes**

```bash
uv run --directory server pytest tests/test_db_schema.py -v
```

Expected:
```
tests/test_db_schema.py::test_all_tables_exist PASSED
1 passed in 0.XXs
```

- [ ] **Step 10: Run all server tests together**

```bash
uv run --directory server pytest -v
```

Expected:
```
tests/test_db_schema.py::test_all_tables_exist PASSED
tests/test_health.py::test_health_returns_ok PASSED
2 passed in 0.XXs
```

- [ ] **Step 11: Notify user — ready to commit**

Tell the user:
> Ready to commit Task 5. Suggested message:
> ```
> git add server/app/db/ server/tests/test_db_schema.py server/.env.example
> git commit -m "feat: database schema + migration + schema verification test"
> ```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered in |
|-----------------|-----------|
| Monorepo root `package.json` with workspaces | Task 1 |
| `.gitignore` | Task 2 |
| `client/` React Router v7 workspace | Task 3 |
| `client/react-router.config.ts` SPA mode | Task 3 |
| `server/pyproject.toml` | Task 4 |
| FastAPI server skeleton | Task 4 |
| `server/.env.example` with all API keys | Task 4 |
| Local PostgreSQL + pgcrypto | Task 5 |
| `agents`, `calls`, `transcripts`, `outcomes`, `audit_log` tables | Task 5 |
| Migrations in `server/app/db/migrations/` | Task 5 |
| Concurrently dev script | Task 1 |

Not in scope for Plan 1 (covered in Plans 2–5):
- Webhook + pipeline services (Plan 2)
- REST API routes for calls and agents (Plan 3)
- Better Auth integration (Plan 4)
- Dashboard views (Plan 5)

### Placeholder scan

No TBDs, TODOs, or placeholder steps. Every code step contains the full file or the exact change.

### Type consistency

No shared types yet — each task is self-contained scaffolding. Types are introduced in Plan 2.
