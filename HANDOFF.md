# InvoiceAI — Project Handoff

Written 2026-10-03. Reflects the repo at commit `4bffba5` (2026-08-21, 30 commits, working tree clean).
Everything below was checked against the code, not recalled — except where marked *(not independently verified)*.

---

## 1. What this is

A multi-tenant B2B SaaS that reads a company's Gmail inbox, pulls invoices out of PDF/image attachments with Gemini, and turns them into structured, searchable, reportable records. Invoices can also be uploaded by hand. Each company is an **organization** with its own isolated data, a shared workspace (invite code), roles, and a Free/Pro subscription.

**State: pre-launch prototype, fully featured, not deployed anywhere.** Runs only on a developer machine. Stripe is in test mode.

**Stack**
| Layer | Tech |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0 (ORM), Alembic, uvicorn |
| Database | PostgreSQL (hosted on Neon). SQLite files in the repo are legacy and unused |
| AI | Google Gemini (`gemini-flash-latest`) — text + vision |
| Email | Gmail API (OAuth, `gmail.readonly`) |
| Payments | Stripe (Checkout, signed webhooks, billing portal) |
| Frontend | React 19, TypeScript, MUI 9, Vite, react-router 7, Recharts |
| CI | GitHub Actions (pytest against an ephemeral Postgres container) |

---

## 2. What's built

**Accounts & tenancy** — register/login/logout; bcrypt passwords; JWT in an httpOnly `SameSite=Lax` cookie (60 min). Organizations own invoices; users join by creating a workspace or via invite code. Two roles, `admin` and `member`; a "last admin" invariant stops an org ever having zero admins. Admin-only: Gmail connect/disconnect, member management, checkout, billing portal. Invite code is redacted from non-admins at the API level.

**Invoice extraction** — manual PDF upload (`/extract`) and automatic via Gmail. Digital PDFs → `pypdf` text → Gemini text path (cheap). Scanned PDFs/images → Gemini vision. Output is forced to JSON, cleaned, then normalized by a Pydantic model: money → exact `Decimal`, dates → ISO `YYYY-MM-DD` (ambiguous numeric dates read day-first), junk → `None`. Duplicate (org, vendor, invoice number) updates the existing row instead of inserting.

**Gmail automation** — OAuth connect (tokens Fernet-encrypted at rest), sync of unread invoice-bearing mail, per-attachment pipeline (download → extract → validate → save), full audit trail in `invoice_processing_logs`. A background scheduler syncs and processes every connected org every 5 min (`SYNC_INTERVAL_SECONDS`, `0` disables). Free-plan orgs are skipped.

**Auto-retry** — transient failures (`download`, `extraction`, `ai_unavailable`, `invalid_ai_response`) are retried at **5 → 15 → 30 min**, then give up. Never retried: `no_account`, `no_invoice_data`. State lives in `email_attachments.retry_count` / `next_retry_at`. No separate scheduler — `process_pending()` also picks up failed attachments whose retry is due, so the existing 5-min loop and the manual "Process" button both drive it. A manual per-attachment retry endpoint exists too.

**Billing** — Free: 20 invoices/month, manual upload only. Pro: $29/mo, unlimited + Gmail automation. Quota is checked *before* any AI call (HTTP 402). Stripe Checkout creates the subscription; the **signature-verified webhook is the only thing allowed to change `organizations.plan`** (the success redirect is cosmetic). Billing portal lets an admin update card / cancel.

**Frontend** — 9 pages (Dashboard with charts, Invoices, Invoice detail, Suppliers, Reports + CSV export, Emails, Billing, Settings, Auth). Light/dark toggle (MUI `useColorScheme`, persisted to `localStorage['mui-mode']`). Lexend headings + Source Sans 3 body. Tables become stacked card lists below the `sm` breakpoint. Emails page polls every 3 s **only while** something is pending/processing, shows a "Live" badge and a recent-activity feed, and has a Status column (icon + retry button, enabled only for failed attachments).

---

## 3. Architecture at a glance

```
Browser (React) ──cookie──▶ FastAPI main.py ──▶ services/*  ──▶ Postgres (SQLAlchemy)
                                   │                │──▶ Gemini   (ai_service)
                                   │                │──▶ Gmail    (gmail_service)
                                   │                └──▶ Stripe   (stripe_service)
                                   └─ lifespan starts scheduler_service (asyncio task, same process)
```

- `main.py` — all routes + auth dependencies (`get_current_user`, `require_admin`). Thin; delegates to services.
- `services/` — one module per concern. **A layer, not microservices**: one process, one database.
- Each service opens its own `SessionLocal()` and commits immediately. There is **no dependency-injected session** (`db.get_db()` exists but is unused). This shapes how tests work (§6).
- Error mapping lives in the web layer: services return machine-readable `code`s, `main.py` maps them to HTTP statuses.
- `processing_service.process_attachment(id)` is the unit of work — a queue worker would call exactly this.

---

## 4. Running it

**Env vars** (`.env`, gitignored — names only): `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `FERNET_KEY`, `GEMINI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`; optional `FRONTEND_URL`, `SYNC_INTERVAL_SECONDS`.

```bash
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head                                   # schema is owned by Alembic, not app startup
.venv/Scripts/python.exe -m uvicorn main:app --port 8000 --reload
cd frontend && npm install && npm run dev              # http://localhost:5173
python -m pytest tests/                                # NOT bare `pytest` — see §7
stripe listen --forward-to localhost:8000/billing/webhook   # prints the whsec_ for STRIPE_WEBHOOK_SECRET
```

---

## 5. Data model

Seven tables: `organizations`, `users`, `invoices`, `email_accounts` (one per org), `email_messages`, `email_attachments`, `invoice_processing_logs`. 11 real foreign keys.

- Money is `NUMERIC(14,2)` / `Decimal` end to end — never float.
- Timestamps are app-generated strings (`%Y-%m-%d %H:%M:%S`); **no DB triggers**. (An early SQLite-only trigger would have silently zeroed billing metering on Postgres — removed.)
- Three Alembic revisions: baseline → money/NUMERIC + indexes → retry columns. See `DATABASE.md` for workflow, drift checks, and the backup/restore drill.

---

## 6. API surface (28 endpoints)

| Area | Endpoints |
|---|---|
| Health | `GET /` |
| Auth | `POST /register`, `POST /login`, `POST /logout`, `GET /me` |
| Invoices | `POST /extract`, `GET /invoices` (search, status, from_date, to_date), `GET`/`PATCH /invoices/{id}`, `GET /dashboard/summary` |
| Gmail | `GET /gmail/connect`, `GET /gmail/callback`, `GET /gmail/status`, `POST /gmail/disconnect` |
| Emails | `POST /emails/sync`, `GET /emails`, `GET /emails/{id}` |
| Processing | `POST /processing/run`, `POST /processing/attachments/{id}/retry`, `GET /processing/jobs` |
| Billing | `GET /billing/usage`, `GET /billing/plans`, `POST /billing/checkout`, `POST /billing/portal`, `POST /billing/webhook` |
| Members | `GET /organization/members`, `PATCH`/`DELETE /organization/members/{id}` |

Out-of-tenant resources return **404, not 403** — a 403 would leak which IDs exist (a competitor could enumerate your customer base).

---

## 7. Testing & CI

**53 tests**, all passing, run in CI on every push/PR.
- `tests/test_ai_normalization.py` (28) — pure Python, ~4 s, no DB.
- `tests/api/` (25) — through the real FastAPI app against a **real Postgres** (`invoiceai_test`): auth, tenant isolation, billing quota, invoice CRUD/filters, roles/permissions edge cases.

Because services commit their own sessions, the usual "roll back each test" pattern can't work. Instead `tests/api/conftest.py` builds the schema from the real Alembic migrations once, then `TRUNCATE`s every table **before** each test (so a failing test's data is inspectable). It refuses to run unless `TEST_DATABASE_URL` contains "test".

No test calls Gemini or Gmail. The full suite takes ~7 min locally (every call crosses the network to Neon).

---

## 8. Gotchas (each one cost real time)

- **`python -m pytest`, not `pytest`** — only `-m` puts the repo root on `sys.path`. CI failed on this.
- **`crypto_service` builds a `Fernet` at import time** — any env (CI included) needs a *validly-shaped* `FERNET_KEY`, not a placeholder string.
- **`alembic revision --autogenerate` emits false `drop_index` ops** for indexes that exist but aren't declared on the models. Read and strip them. NOT NULL columns on a non-empty table need a `server_default`.
- **Stripe moved `current_period_end` onto subscription *items*** (new accounts have no top-level field). Read `subscription["items"]["data"][0]["current_period_end"]`.
- **`email-validator` rejects the `.test` TLD** — use `example.com` for fixtures.
- **Vite HMR shows stale errors** after rapid multi-file edits (e.g. "X is not defined"). Open a fresh tab before believing it.
- **uvicorn `--reload` is flaky on Windows** — restart if a new route 404s.
- **Windows PATH** — a CLI installed via winget isn't visible to already-open terminals (including VS Code's) until they restart. The Stripe CLI winget id is `Stripe.StripeCli` (casing matters).
- **JWTs expire in 60 min** — a long browser session silently drops to the login screen.
- **Gemini** sometimes returns transient 503s / truncated JSON; handled by retry + `invalid_ai_response`.

---

## 9. Not done / known risks

Be honest with yourself about these before charging real customers.

**Deployment & ops**
- **Not deployed anywhere.** An early Vercel attempt failed (serverless can't host this). Planned: frontend → Vercel, API → Render, DB → managed Postgres (already proven on Neon).
- `secure=False` on both cookies (`main.py:283`, `:312`), CORS origin and frontend `API_URL` hardcoded to `localhost` — all dev-only.
- No Dockerfile, no rate limiting, no error monitoring (Sentry), no health/readiness probes, no CSRF tokens (only `SameSite=Lax`).
- No automated backups. One manual backup + restore drill was run; nothing recurs.
- The scheduler runs **inside the web process** — a second instance would double-process every inbox. Needs a real queue before scaling out.

**Billing**
- Stripe is **test mode only**; the webhook secret in `.env` comes from `stripe listen` and is a *local-session* secret — production needs its own endpoint and secret. The CLI login expires after 90 days.
- The webhook handles only `checkout.session.completed` and `customer.subscription.deleted`. **`customer.subscription.updated` and `invoice.payment_failed` are not handled** — a card that starts failing won't flip the org to past-due.

**Gmail / AI**
- Google OAuth app is in **Testing** mode (only listed test users can connect). `gmail.readonly` is a restricted scope — production needs Google verification.
- AI accuracy has never been measured and there is **no human-review/correct step** — a wrong extraction can only be fixed by editing status/due date. This is the likeliest objection from a finance buyer.
- `gemini-flash-latest` is an unpinned alias; behavior can change under you. Invoice text is sent to a third-party LLM with no documented DPA/disclosure.
- Prompt injection via invoice text is not defended against.

**Quality**
- **The entire Gmail/email pipeline and the auto-retry logic have no automated tests** (verified live only). Scheduler, Stripe, and the frontend are also untested.
- `/extract` buffers the whole upload before checking size; no pagination on list endpoints; no password reset or email verification.
- Visual design was verified by DOM/computed-style checks only. The Browser pane in this environment couldn't capture screenshots, and **no human has recorded a visual review** of the redesign.

**Score:** the 2026-07-29/08-03 audit (`AUDIT.md`) rated production readiness **42/100**. Since then these audit findings were fixed: float money, the SQLite-trigger billing bug, SQLite itself, zero tests, no CI, no payments. **It has not been re-run**, so there is no updated score — don't quote 42 as current.

---

## 10. Suggested next steps

1. **Make it deployable** — secure cookies, env-driven CORS / `API_URL` / `FRONTEND_URL`, Dockerfile, rate limiting, Sentry, health check. (Audit's own next step.)
2. **Deploy** — Vercel + Render + Postgres; add the prod OAuth redirect URI; create a production Stripe webhook endpoint.
3. **Close the Stripe gaps** — handle `subscription.updated` / `invoice.payment_failed`; live-mode checklist.
4. **Test the untested** — Gmail pipeline + retry logic with mocked Gmail/Gemini.
5. **Add a review step** and measure extraction accuracy on real invoices.
6. **Move the scheduler to a real queue** before running more than one instance.
7. **Re-run the audit** to get an honest current score.

---

## 11. Repo housekeeping

- `PROJECT_PROGRESS.md` and `TODO.md` are **gitignored and stale** (last touched 2026-07-29). Ignore them; this file and `DATABASE.md` supersede them.
- `invoice.db`, `invoice.db.pre-sprint1-backup`, `invoice.txt`, and `invoices/` (sample/scanned PDFs) are legacy/fixtures. The app no longer reads SQLite.
- The dev database holds throwaway accounts and orgs from testing (one has a real Gmail connected, plus a seeded fixture attachment). Credentials are deliberately **not** recorded here — create fresh ones via `/register`.
- `AUDIT.md` — full technical due-diligence review (18 sections). `DATABASE.md` — schema ownership, migration workflow, backup drill, the Postgres cutover story.
