# Voice Call Logger

A FastAPI-powered voice pipeline that receives outbound call recordings via Twilio webhook, transcribes them with Whisper, redacts PHI before anything hits the database, extracts structured outcomes via Claude, and surfaces everything in a clean audit-aware dashboard.

Features:
**OK to consider open-source alternatives**

Twilio webhook + call recording
Whisper STT transcription
Claude structured outcome extraction
PHI redaction via Presidio
Audit log table
FastAPI REST endpoints
Supabase + pgcrypto at rest
Dashboard with call log + outcome viewer

For any technologies, would prefer to use context7

```bash
Twilio          → webhook trigger + call recording delivery
FastAPI         → core pipeline service (Python)
OpenAI Whisper  → speech-to-text (local or API)
Presidio        → PHI detection + redaction
Claude API      → structured outcome extraction
Supabase        → Postgres + pgcrypto for at-rest encryption
Next.js         → dashboard frontend
Railway/Render  → deploy the FastAPI service publicly
```

For db for now, would like to consider just working locally with a postgres db with a prisma adapter

Frontend dashboard, looking more for React + React Router V7 (use context7)

authentication considering betterauth (use context7)

Also consider having the ability to build different voice agents for specific things/featurs/logging