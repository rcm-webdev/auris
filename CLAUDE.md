# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

---

## Git workflow

**Never create git commits.** When work reaches a logical commit point, stop and tell the user with a suggested commit message. The user commits manually.

---

## What this project is

A PHI-aware voice call logging pipeline. Twilio delivers call recordings → Whisper transcribes → Presidio redacts PHI → Claude extracts structured outcomes → dashboard surfaces everything. Monorepo: `client/` (React + React Router v7, SPA) + `server/` (FastAPI, Python).

---

## Commands

### Run everything

```bash
npm run dev          # client (port 5173) + server (port 8000) via concurrently
npm run dev:client   # client only
npm run dev:server   # server only
```

### Client (from repo root)

```bash
npm run dev -w client          # dev server
npm run build -w client        # production build
npm run typecheck -w client    # type check
```

### Server (from repo root)

```bash
uv run --directory server pytest                        # all tests
uv run --directory server pytest tests/test_foo.py -v  # single file
uv run --directory server pytest -k "test_name" -v     # single test
uv run --directory server uvicorn app.main:app --reload --port 8000
```

### Database

```bash
psql franky_dev < server/app/db/migrations/001_initial.sql  # apply migration
psql franky_dev                                              # open psql shell
```

### Better Auth (client workspace)

```bash
npm run auth:migrate -w client   # apply Better Auth schema (if script added)
npx @better-auth/cli@latest migrate --config client/app/lib/auth.ts
```

---

## Architecture

### Monorepo layout

| Directory | Runtime | Package manager |
|-----------|---------|----------------|
| `client/` | Node 20, React Router v7 (SPA mode) | npm workspaces |
| `server/` | Python 3.11+, FastAPI | uv |

Both share one local Postgres database (`DATABASE_URL`). No separate auth service.

### Auth across two runtimes

Better Auth runs inside the React Router v7 Node server (`client/app/lib/auth.ts`). FastAPI validates sessions by querying the `sessions` table directly via asyncpg — no token exchange. The session cookie from the browser is passed to FastAPI, which reads the session row and returns the user or 401.

Key files:
- `client/app/lib/auth.ts` — Better Auth server instance; pg Pool; email+password; 7-day sessions
- `client/app/lib/auth-client.ts` — `createAuthClient` with `useSession()` hook
- `client/app/routes/api.auth.$.ts` — catch-all that mounts Better Auth on `/api/auth/*`
- `client/app/routes/_protected.tsx` — layout route; redirects to `/login` if no session
- `server/app/api/deps.py` — `get_current_session()` FastAPI dependency; reads cookie → queries `sessions` table → returns user or raises 401

### Pipeline (the core of the product)

All triggered by `POST /api/webhooks/recording`. Runs as a FastAPI `BackgroundTask`.

```
Twilio webhook → upsert call row (status: pending)
  → transcription.py   fetch audio from Twilio URL → Whisper API → raw text  (status: transcribed)
  → redaction.py       Presidio PHI detection + [REDACTED] replacement        (status: redacted)
                       write redacted_text to transcripts table
                       raw text is discarded here — it never touches the DB
  → extraction.py      Claude structured extraction → outcomes table           (status: extracted)
  → any failure        status: failed + audit row
```

**PHI boundary:** `server/app/services/redaction.py` is the only place raw transcript text exists. Raw text must never be logged, stored, or passed to any other service. This is the most critical invariant in the codebase.

### Database

Plain SQL migrations in `server/app/db/migrations/`. Apply manually with `psql`. No ORM — raw asyncpg queries throughout the server. Schema is designed to be Supabase-compatible (no schema changes needed to migrate).

Encrypted column: `transcripts.redacted_text` uses pgcrypto at rest.

### API conventions

All routes under `/api`. Session cookie validated on every non-webhook route via the `get_current_session()` dependency. Webhook route validates Twilio request signature instead.

List responses: `{ data: [...], total: int, page: int, limit: int }`.

---

## Key decisions (don't relitigate without good reason)

| Decision | Rationale |
|----------|-----------|
| Whisper API (not local) | Zero infra for MVP; swap to faster-whisper later |
| No ORM — raw asyncpg | Presidio and anthropic SDK are Python-native; no need to add Prisma/Drizzle on the Python side |
| Postgres for Better Auth sessions (not Redis) | Single `DATABASE_URL`; FastAPI cross-queries the `sessions` table |
| React Router v7 SPA mode | Lighter than Next.js; deploys to Vercel |
| `BackgroundTask` not Celery | Sufficient for MVP volume; Celery added later if needed |
| Local Postgres → Supabase later | Schema is identical; `DATABASE_URL` swap is the only migration |

---

## Library docs

Always use **context7** when working with: React Router v7, Better Auth, FastAPI, asyncpg, Presidio, Anthropic SDK, OpenAI SDK, Twilio. These evolve fast and training data may be stale.

```
# In any task involving these libraries, resolve the library ID first:
mcp__plugin_context7_context7__resolve-library-id
mcp__plugin_context7_context7__query-docs
```

---

## Custom agents

Located in `.claude/agents/`. Invoke via the Agent tool when the task matches:

| Agent | When to use |
|-------|-------------|
| `betterauth-security-expert` | Any Better Auth config, session management, or auth security review |
| `monorepo-structure-reviewer` | Adding packages, restructuring workspaces, reviewing workspace layout |
| `sql-query-expert` | Complex queries, schema changes, migration review |
| `test-runner` | Running Playwright E2E or Vitest component tests |
| `pair-programming-mentor` | Explaining newly written code across multiple files |

---

## Implementation plans

Plans live in `docs/superpowers/plans/`. The project is built in five sequential plans:

1. `2026-05-08-plan-1-scaffold-database.md` — Monorepo scaffold + DB schema (current)
2. Plan 2 — FastAPI pipeline (webhook → transcription → redaction → extraction)
3. Plan 3 — FastAPI REST API (agents, calls, auth dependency)
4. Plan 4 — React + Better Auth
5. Plan 5 — Dashboard views

Full design spec: `docs/superpowers/specs/2026-05-08-voice-call-logger-design.md`
