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
  agent_id         UUID REFERENCES agents(id),  -- nullable: populated from Twilio custom param; may be absent
  twilio_call_sid  TEXT UNIQUE NOT NULL,
  recording_url    TEXT,
  duration_seconds INTEGER,
  called_at        TIMESTAMPTZ,
  status           TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'transcribed', 'redacted', 'extracted', 'failed'))
);

CREATE INDEX ON calls (agent_id);
CREATE INDEX ON calls (status);

-- Redacted transcripts only — raw text is never persisted.
-- redacted_text is stored via pgp_sym_encrypt() at the application layer (redaction.py).
-- Reads use pgp_sym_decrypt() with the ENCRYPTION_KEY env var. Column type is TEXT to hold ciphertext.
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

-- summary, disposition, next_action are nullable: Claude extraction may produce partial results
-- depending on call content. A row always exists once extraction runs; fields may be empty.

-- Immutable append-only audit trail
CREATE TABLE audit_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id    UUID REFERENCES calls(id),
  event      TEXT NOT NULL,
  actor      TEXT NOT NULL DEFAULT 'system',
  metadata   JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
