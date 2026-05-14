# Plan 4: React + Better Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up a working login/logout flow with Better Auth and add typed API client stubs so protected routes are reachable and ready for Plan 5 dashboard content.

**Architecture:** Better Auth runs inside the React Router v7 Node server; the session cookie is sent with `credentials: "include"` to FastAPI which validates it against the shared `session` table. Protected routes redirect to `/login` when no session exists.

**Tech Stack:** React Router v7 (SPA mode), Better Auth 1.x, Tailwind CSS v4, TypeScript strict mode

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `client/app/routes.ts` | Wire layout + login + child routes |
| Modify | `client/app/routes/_protected.tsx` | Add nav header with logout |
| Create | `client/app/routes/login.tsx` | Email+password sign-in/sign-up form |
| Create | `client/app/routes/_index.tsx` | Dashboard placeholder (Plan 5 content goes here) |
| Create | `client/app/routes/calls.$id.tsx` | Call detail placeholder |
| Create | `client/app/routes/agents.tsx` | Agents list placeholder |
| Create | `client/app/lib/api.ts` | Typed fetch wrappers → FastAPI |
| Delete | `client/app/routes/home.tsx` | Replaced by `_index.tsx` under protected layout |
| Delete | `client/app/welcome/` | Stale scaffold — not used |

---

## Task 1: Verify Better Auth DB tables

**Files:**
- Read: `server/app/db/migrations/002_better_auth.sql`

- [ ] **Step 1: Check whether the tables already exist**

```bash
psql franky_dev -c 'SELECT COUNT(*) FROM "user";'
```

Expected outputs:
- If tables exist: `count = 0` (or any number)
- If tables are missing: `ERROR: relation "user" does not exist`

- [ ] **Step 2: Apply migration if tables are missing**

Only run this if Step 1 returned an error:

```bash
psql franky_dev < server/app/db/migrations/002_better_auth.sql
```

Expected: no errors, prompts finish with `CREATE TABLE`, `CREATE INDEX`, `ALTER TABLE`.

- [ ] **Step 3: Verify all four tables exist**

```bash
psql franky_dev -c '\dt' | grep -E 'user|session|account|verification'
```

Expected: four rows — `user`, `session`, `account`, `verification`.

---

## Task 2: Update route config

**Files:**
- Modify: `client/app/routes.ts`

- [ ] **Step 1: Replace routes.ts with the new route tree**

```ts
import {
  type RouteConfig,
  index,
  layout,
  route,
} from "@react-router/dev/routes";

export default [
  route("login", "routes/login.tsx"),
  route("api/auth/*", "routes/api.auth.$.ts"),
  layout("routes/_protected.tsx", [
    index("routes/_index.tsx"),
    route("calls/:id", "routes/calls.$id.tsx"),
    route("agents", "routes/agents.tsx"),
  ]),
] satisfies RouteConfig;
```

- [ ] **Step 2: Verify type generation still works**

```bash
npm run typecheck -w client
```

Expected: no errors (React Router will regenerate `.react-router/types/` as needed).

---

## Task 3: Create login page

**Files:**
- Create: `client/app/routes/login.tsx`

- [ ] **Step 1: Create login.tsx**

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { signIn, signUp } from "~/lib/auth-client";

export function meta() {
  return [{ title: "Sign in — Franky" }];
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "signin") {
        const { error: err } = await signIn.email({ email, password });
        if (err) {
          setError(err.message ?? "Sign in failed");
          return;
        }
      } else {
        const { error: err } = await signUp.email({ email, password, name });
        if (err) {
          setError(err.message ?? "Sign up failed");
          return;
        }
      }
      navigate("/");
    } finally {
      setLoading(false);
    }
  }

  function toggleMode() {
    setMode((m) => (m === "signin" ? "signup" : "signin"));
    setError("");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow p-8">
        <h1 className="text-2xl font-semibold mb-6 text-center">
          {mode === "signin" ? "Sign in" : "Create account"}
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "signup" && (
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700"
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700"
            />
          </div>
          <div>
            <label
              className="block text-sm font-medium mb-1"
              htmlFor="password"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white rounded py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
          >
            {loading ? "…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="text-sm text-center mt-4 text-gray-500">
          {mode === "signin" ? "No account?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="text-blue-600 hover:underline cursor-pointer"
            onClick={toggleMode}
          >
            {mode === "signin" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck -w client
```

Expected: no errors.

---

## Task 4: Update protected layout with nav

**Files:**
- Modify: `client/app/routes/_protected.tsx`

- [ ] **Step 1: Replace _protected.tsx with layout + nav**

```tsx
import { Outlet, useNavigate, Link } from "react-router";
import { useEffect } from "react";
import { signOut, useSession } from "~/lib/auth-client";

export default function ProtectedLayout() {
  const { data: session, isPending } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isPending && !session) {
      navigate("/login", { replace: true });
    }
  }, [session, isPending, navigate]);

  if (isPending || !session) return null;

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-950">
      <header className="h-14 border-b bg-white dark:bg-gray-900 flex items-center px-6 justify-between shrink-0">
        <nav className="flex items-center gap-6">
          <span className="font-semibold text-sm">Franky</span>
          <Link
            to="/"
            className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          >
            Calls
          </Link>
          <Link
            to="/agents"
            className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          >
            Agents
          </Link>
        </nav>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{session.user.email}</span>
          <button
            type="button"
            onClick={handleSignOut}
            className="text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck -w client
```

Expected: no errors.

---

## Task 5: Create protected route stubs

**Files:**
- Create: `client/app/routes/_index.tsx`
- Create: `client/app/routes/calls.$id.tsx`
- Create: `client/app/routes/agents.tsx`

These are intentionally minimal — Plan 5 fills in the content.

- [ ] **Step 1: Create _index.tsx (dashboard placeholder)**

```tsx
export function meta() {
  return [{ title: "Calls — Franky" }];
}

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">Calls</h1>
      <p className="text-sm text-gray-500">Dashboard — coming in Plan 5.</p>
    </div>
  );
}
```

- [ ] **Step 2: Create calls.$id.tsx (call detail placeholder)**

```tsx
import { useParams } from "react-router";

export function meta() {
  return [{ title: "Call Detail — Franky" }];
}

export default function CallDetailPage() {
  const { id } = useParams();
  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">Call {id}</h1>
      <p className="text-sm text-gray-500">Call detail — coming in Plan 5.</p>
    </div>
  );
}
```

- [ ] **Step 3: Create agents.tsx (agents placeholder)**

```tsx
export function meta() {
  return [{ title: "Agents — Franky" }];
}

export default function AgentsPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">Agents</h1>
      <p className="text-sm text-gray-500">Agents list — coming in Plan 5.</p>
    </div>
  );
}
```

- [ ] **Step 4: Run typecheck**

```bash
npm run typecheck -w client
```

Expected: no errors.

---

## Task 6: Create typed API client

**Files:**
- Create: `client/app/lib/api.ts`

- [ ] **Step 1: Create api.ts with types + fetch wrappers**

The types mirror `server/app/models/schemas.py` exactly. Fetch calls include `credentials: "include"` so the session cookie travels cross-origin to FastAPI on port 8000.

```ts
const BASE = import.meta.env.VITE_API_URL as string;

// ── Types ──────────────────────────────────────────────────────────────────

export interface AgentSummary {
  id: string;
  name: string;
}

export interface CallListItem {
  id: string;
  twilio_call_sid: string;
  duration_seconds: number | null;
  called_at: string | null;
  status: "pending" | "transcribed" | "redacted" | "extracted" | "failed";
  agent: AgentSummary | null;
}

export interface CallListResponse {
  data: CallListItem[];
  total: number;
  page: number;
  limit: number;
}

export interface TranscriptDetail {
  redacted_text: string;
  whisper_model: string | null;
}

export interface OutcomeDetail {
  summary: string | null;
  disposition: string | null;
  next_action: string | null;
}

export interface CallDetail {
  id: string;
  twilio_call_sid: string;
  recording_url: string | null;
  duration_seconds: number | null;
  called_at: string | null;
  status: "pending" | "transcribed" | "redacted" | "extracted" | "failed";
  agent: AgentSummary | null;
  transcript: TranscriptDetail | null;
  outcome: OutcomeDetail | null;
}

export interface AuditEvent {
  id: string;
  event: string;
  actor: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditListResponse {
  data: AuditEvent[];
}

export interface AgentDetail {
  id: string;
  name: string;
  email: string;
  created_at: string;
  total_calls: number;
  completed_calls: number;
}

export interface AgentListResponse {
  data: AgentDetail[];
}

export interface AgentCreate {
  name: string;
  email: string;
}

export interface CallListParams {
  agent_id?: string;
  status?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  limit?: number;
}

// ── Internal fetch wrapper ─────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Public API client ──────────────────────────────────────────────────────

export const api = {
  calls: {
    list: (params: CallListParams = {}): Promise<CallListResponse> => {
      const qs = new URLSearchParams();
      if (params.agent_id) qs.set("agent_id", params.agent_id);
      if (params.status) qs.set("status", params.status);
      if (params.from_date) qs.set("from_date", params.from_date);
      if (params.to_date) qs.set("to_date", params.to_date);
      if (params.page != null) qs.set("page", String(params.page));
      if (params.limit != null) qs.set("limit", String(params.limit));
      const query = qs.toString();
      return apiFetch<CallListResponse>(
        `/api/calls${query ? `?${query}` : ""}`,
      );
    },
    get: (id: string): Promise<CallDetail> =>
      apiFetch<CallDetail>(`/api/calls/${id}`),
    getAudit: (id: string): Promise<AuditListResponse> =>
      apiFetch<AuditListResponse>(`/api/calls/${id}/audit`),
  },

  agents: {
    list: (): Promise<AgentListResponse> =>
      apiFetch<AgentListResponse>("/api/agents"),
    get: (id: string): Promise<AgentDetail> =>
      apiFetch<AgentDetail>(`/api/agents/${id}`),
    create: (body: AgentCreate): Promise<AgentDetail> =>
      apiFetch<AgentDetail>("/api/agents", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },
};
```

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck -w client
```

Expected: no errors.

---

## Task 7: Remove stale welcome scaffold

**Files:**
- Delete: `client/app/routes/home.tsx`
- Delete: `client/app/welcome/welcome.tsx`
- Delete: `client/app/welcome/logo-dark.svg`
- Delete: `client/app/welcome/logo-light.svg`

- [ ] **Step 1: Delete the files**

```bash
rm client/app/routes/home.tsx
rm client/app/welcome/welcome.tsx
rm client/app/welcome/logo-dark.svg
rm client/app/welcome/logo-light.svg
rmdir client/app/welcome
```

- [ ] **Step 2: Run typecheck to confirm no dangling imports**

```bash
npm run typecheck -w client
```

Expected: no errors.

---

## Task 8: Manual smoke test

Start both servers and verify the complete auth flow in the browser.

- [ ] **Step 1: Start the dev stack**

```bash
npm run dev
```

Expected: client on http://localhost:5173, server on http://localhost:8000.

- [ ] **Step 2: Test unauthenticated redirect**

Open http://localhost:5173 in a browser. Expected: browser redirects to `/login`.

- [ ] **Step 3: Sign up**

Fill the sign-up form (name, email, password). Click "Sign up". Expected: redirected to `/` showing the Calls dashboard placeholder with the nav header.

- [ ] **Step 4: Verify session persistence**

Hard-refresh the page (Ctrl+Shift+R). Expected: still on `/` with session intact, not redirected to `/login`.

- [ ] **Step 5: Navigate between protected routes**

Click "Agents" in the nav. Expected: `/agents` renders placeholder. Click "Calls" — returns to `/`. Navigate directly to http://localhost:5173/calls/test-id — renders call detail placeholder.

- [ ] **Step 6: Sign out**

Click "Sign out" in the nav. Expected: redirected to `/login`.

- [ ] **Step 7: Verify post-logout protection**

Navigate to http://localhost:5173/. Expected: redirected to `/login`.

- [ ] **Step 8: Sign in with the account you created**

Use the sign-in form with the credentials from Step 3. Expected: redirected to `/` — dashboard placeholder visible.

---

## Done

Plan 4 is complete when:
- `npm run typecheck -w client` passes with zero errors
- All 8 smoke-test steps pass
- `api.ts` exports `api.calls.*` and `api.agents.*` typed wrappers ready for Plan 5
