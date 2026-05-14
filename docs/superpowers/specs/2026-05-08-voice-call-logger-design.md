# Voice Call Logger — Design Spec

**Date:** 2026-05-08
**Status:** Approved

---

## Overview

A PHI-aware voice call logging pipeline. Outbound calls are recorded via Twilio, transcribed with the OpenAI Whisper API, redacted of PHI by Presidio, structured by Claude, and surfaced in a React dashboard. Built as an MVP monorepo, pipeline-first, reviewed step-by-step.

---

## Key Decisions

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Transcription | OpenAI Whisper API | Zero infra for MVP; swap to faster-whisper later if needed |
| PHI redaction | Microsoft Presidio | Purpose-built, HIPAA-relevant entity types out of the box |
| Auth | Better Auth (email+password) | Native React Router v7 integration, TypeScript-native, sessions in shared DB |
| Database | Local PostgreSQL + pgcrypto | Single `DATABASE_URL`; Supabase-ready later with no schema changes |
| Frontend | React + React Router v7 (Vite) | Lighter than Next.js, SPA mode → Vercel |
| Backend | FastAPI (Python) | Async, Presidio + anthropic SDK are Python-native |
| Deployment | Vercel (client) + Railway/Render (server) | Optimal per-service, deferred to post-MVP |
| Build order | Pipeline-first | Core value is the pipeline; dashboard requirements become clear once data flows |

---

## Monorepo Structure

```
franky/
├── package.json              # root — workspaces: ["client"], concurrently dev scripts
├── package-lock.json
├── .gitignore
├── client/                   # npm workspace — React + React Router v7
│   ├── package.json
│   ├── vite.config.ts
│   ├── react-router.config.ts
│   ├── .env.example
│   └── app/
│       ├── root.tsx
│       ├── routes.ts
│       ├── routes/
│       │   ├── api.auth.$.ts       # Better Auth catch-all → /api/auth/*
│       │   ├── login.tsx           # Sign-in form
│       │   ├── _protected.tsx      # Layout route — session guard
│       │   ├── _index.tsx          # Call log dashboard
│       │   ├── calls.$id.tsx       # Call detail + outcome viewer
│       │   └── agents.tsx          # Agent management
│       └── lib/
│           ├── auth.ts             # Better Auth server instance (pg Pool)
│           ├── auth-client.ts      # createAuthClient (better-auth/react)
│           └── api.ts              # Typed fetch wrappers → FastAPI
├── server/                   # Python — FastAPI pipeline service
│   ├── pyproject.toml
│   ├── .env.example
│   ├── tests/
│   └── app/
│       ├── main.py               # FastAPI app + router registration
│       ├── api/
│       │   ├── webhooks.py       # POST /api/webhooks/recording
│       │   ├── calls.py          # GET /api/calls, GET /api/calls/:id
│       │   ├── agents.py         # GET/POST /api/agents
│       │   └── deps.py           # get_current_session() dependency
│       ├── services/
│       │   ├── transcription.py  # Whisper API client
│       │   ├── redaction.py      # Presidio PHI redaction
│       │   ├── extraction.py     # Claude structured outcome extraction
│       │   └── storage.py        # Postgres writes via asyncpg
│       ├── models/
│       │   └── schemas.py        # Pydantic request/response models
│       └── db/
│           └── migrations/       # Plain SQL files, run manually
└── docs/
    ├── details.md
    └── superpowers/
        └── specs/
            └── 2026-05-08-voice-call-logger-design.md
```

---

## Data Model

```sql
-- Enable encryption extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Call agents: human reps making outbound calls
CREATE TABLE agents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  email         TEXT UNIQUE NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW()
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
    CHECK (status IN ('pending','transcribed','redacted','extracted','failed'))
);

-- Redacted transcripts only — raw text is never stored
CREATE TABLE transcripts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id       UUID UNIQUE REFERENCES calls(id),
  redacted_text TEXT NOT NULL,   -- encrypted at rest via pgcrypto
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

-- Better Auth managed (auto-migrated by Better Auth CLI):
-- users, sessions, accounts
```

---

## Pipeline Flow

```
Twilio (call ends)
  │
  ▼
POST /api/webhooks/recording
  │
  ├─ 1. Upsert call row            status: pending
  │      agent_id from Twilio custom param
  │
  ├─ 2. transcription.py           status: transcribed
  │      Fetch audio from Twilio recording URL
  │      POST to OpenAI Whisper API → raw text
  │      audit: transcription_completed
  │
  ├─ 3. redaction.py               status: redacted
  │      Presidio PHI detection + [REDACTED] replacement
  │      Write redacted_text to transcripts table
  │      Discard raw text — never touches DB
  │      audit: phi_redacted
  │
  ├─ 4. extraction.py              status: extracted
  │      Send redacted_text to Claude with structured prompt
  │      Parse → summary, disposition, next_action
  │      Write to outcomes table
  │      audit: outcome_extracted
  │
  └─ On any failure                status: failed
         audit: step_failed + error detail
```

Pipeline runs in a FastAPI `BackgroundTask` for MVP. Celery queue added later if volume demands.

---

## API Contract

All routes prefixed `/api`. Session cookie validated via `get_current_session()` FastAPI dependency on all non-webhook routes.

### Webhooks
```
POST  /api/webhooks/recording     # public, Twilio signature validated
```

### Agents
```
GET   /api/agents                 # list all agents
POST  /api/agents                 # create agent { name, email }
GET   /api/agents/:id             # agent detail + call stats
```

### Calls
```
GET   /api/calls                  # paginated list
                                  # query: agent_id, status, from_date, to_date, page, limit
GET   /api/calls/:id              # full detail: call + transcript + outcome
GET   /api/calls/:id/audit        # ordered audit events
```

### Response shapes

**List:** `{ data: [...], total: int, page: int, limit: int }`

**Call detail:**
```json
{
  "id": "uuid",
  "agent": { "id": "uuid", "name": "Jane Smith" },
  "called_at": "2026-05-08T14:00:00Z",
  "duration_seconds": 182,
  "status": "extracted",
  "transcript": { "redacted_text": "Hello [REDACTED], calling about..." },
  "outcome": {
    "summary": "Prospect expressed interest in Q3 follow-up",
    "disposition": "callback",
    "next_action": "Schedule call for July"
  }
}
```

---

## Authentication (Better Auth)

Better Auth runs inside the React Router v7 Node server. FastAPI validates sessions via the shared Postgres DB — no separate auth service.

| Layer | File | Role |
|-------|------|------|
| Server config | `client/app/lib/auth.ts` | Better Auth instance, pg Pool, email+password, 7-day sessions |
| Client SDK | `client/app/lib/auth-client.ts` | `createAuthClient` from `better-auth/react`, `useSession()` hook |
| HTTP handler | `client/app/routes/api.auth.$.ts` | Mounts Better Auth on `/api/auth/*` |
| Route guard | `client/app/routes/_protected.tsx` | Layout route — redirects to `/login` if no session |
| FastAPI dep | `server/app/api/deps.py` | Reads session cookie → queries `sessions` table → returns user or 401 |

---

## Dashboard Routes

| Route | View |
|-------|------|
| `/login` | Email + password sign-in |
| `/` | Call log table — agent, timestamp, duration, disposition, status badge. Filterable by agent + date. |
| `/calls/:id` | Call detail — metadata, redacted transcript, outcome panel, audit log timeline |
| `/agents` | Agent list with call counts + create agent form |

---

## Critical Files

| File | Why it matters |
|------|---------------|
| `server/app/api/webhooks.py` | Entry point for the entire pipeline |
| `server/app/services/redaction.py` | PHI boundary — raw text must never leave this module |
| `server/app/api/deps.py` | Session validation — gates all protected FastAPI routes |
| `client/app/lib/auth.ts` | Better Auth server config — session lifetime, DB connection |
| `client/app/routes/api.auth.$.ts` | Better Auth HTTP handler |
| `server/app/db/migrations/` | Source of truth for schema |
