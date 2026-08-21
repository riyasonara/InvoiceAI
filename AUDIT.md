# InvoiceAI — Technical Due Diligence Audit

**Audit date:** 2026-07-29
**Scope:** full repository at commit `1ed87f7` + 14 uncommitted working-tree changes (roles/permissions + billing Feature 1)
**Codebase size:** 4,538 lines of application code (Python + TypeScript), 58 tracked files
**Method:** direct file inspection, live database introspection, dependency manifest review, git history. No conclusions drawn from assumption.

---

## 1. Repository Understanding

### What the product does
An **AI-powered Accounts Payable (AP) automation platform**. Suppliers email invoices; the system ingests them automatically, extracts structured data with an LLM, stores them per-tenant, tracks payment status, and reports on spend. Manual PDF upload is also supported.

### Target customers
Evidence-based read: **SMB and lower-mid-market finance/AP teams** (roughly 5–200 employees) processing tens-to-hundreds of supplier invoices monthly. Signals: workspace/invite model rather than SSO, a single shared Gmail inbox per workspace, GST as a first-class extracted field (India/APAC/Commonwealth VAT-style tax), and a $29/month price point in `plans.py`.

### Verified technology inventory

| Layer | Technology | Evidence |
|---|---|---|
| Backend | Python, FastAPI 0.139.2, Uvicorn 0.51.0 | `requirements.txt`, `main.py` |
| ORM | SQLAlchemy 2.0.51 (typed `Mapped[]` style) | `models.py`, `db.py` |
| Database | SQLite (`invoice.db`); `DATABASE_URL` allows Postgres | `db.py:15` |
| AI | Google Gemini via `google-genai` 2.11.0, model `gemini-flash-latest` | `services/ai_service.py:152` |
| PDF | `pypdf` 6.14.2 | `readers/pdf_reader.py` |
| Auth | JWT (PyJWT 2.13.0, HS256) in an httpOnly cookie; bcrypt 5.0.0 | `services/auth_service.py` |
| Crypto | `cryptography` 49.0.0 — Fernet, for OAuth tokens at rest | `services/crypto_service.py` |
| Email | Gmail API (`google-api-python-client` 2.198.0), OAuth 2.0 (`google-auth-oauthlib` 1.4.0), scope `gmail.readonly` | `services/gmail_service.py` |
| Frontend | React 19, TypeScript 7, Vite 8, MUI 9, Recharts 3, React Router 7 | `frontend/package.json` |
| Background jobs | In-process `asyncio` loop in FastAPI lifespan | `services/scheduler_service.py` |
| Payments | **Not integrated.** Plan/quota logic only; no Stripe SDK, no `STRIPE_*` env keys | `plans.py`, `services/billing_service.py`, `.env` |
| CI/CD | **None** | no `.github/`, no `Dockerfile`, no deploy config |
| Tests | **None** | no `tests/`, no pytest/vitest config |
| Migrations | **None** (hand-rolled `ALTER TABLE` in service startup functions) | no `alembic/` |

### Architecture diagram

```
┌────────────────────────────────────────────────────────────────────┐
│  BROWSER (React 19 + TS + MUI, Vite dev :5173)                     │
│  Pages: Dashboard · Invoices · InvoiceDetail · Suppliers ·         │
│         Reports · Emails · Billing · Settings · AuthScreen         │
│  api.ts → fetch(credentials:"include")   [API_URL HARDCODED]       │
└───────────────────────────────┬────────────────────────────────────┘
                                │ httpOnly cookie (JWT, SameSite=Lax)
                                │ CORS allow_origins=[localhost:5173]
┌───────────────────────────────▼────────────────────────────────────┐
│  FastAPI (main.py, 602 lines — 28 routes, all handlers thin)       │
│  Dependencies: get_current_user → require_admin                    │
│  Guards on /extract: quota(402) → mime(415) → size(413)            │
│  Lifespan: starts in-process auto-sync loop                        │
└───┬─────────────┬───────────────┬──────────────┬───────────────────┘
    │             │               │              │
┌───▼──────┐ ┌────▼─────────┐ ┌───▼──────────┐ ┌─▼──────────────────┐
│ auth_    │ │ invoice_     │ │ email_ /     │ │ billing_ /         │
│ service  │ │ service      │ │ gmail_ /     │ │ plans.py           │
│ user_    │ │ database_    │ │ processing_ /│ │ (quota + feature   │
│ org_     │ │ service      │ │ scheduler_   │ │  gating)           │
│ service  │ │ ai_service   │ │ crypto_      │ │                    │
└───┬──────┘ └────┬─────────┘ └───┬──────────┘ └────────────────────┘
    │             │               │
    │        ┌────▼─────────┐ ┌───▼──────────┐
    │        │ Gemini API   │ │ Gmail API    │
    │        │ (flash-latest│ │ (readonly)   │
    │        │  JSON mode)  │ │ OAuth2       │
    │        └──────────────┘ └──────────────┘
    │
┌───▼────────────────────────────────────────────────────────────────┐
│  SQLite via SQLAlchemy — 7 tables                                  │
│  organizations ─┬─< users (role: admin|member)                     │
│                 ├─< invoices (unique: org_id+vendor+invoice_number) │
│                 └─< email_accounts ─< email_messages               │
│                                        └─< email_attachments       │
│                                             └─ invoice_processing_logs│
│  ⚠ ONE real index. created_at set by a SQLite-only TRIGGER.        │
└────────────────────────────────────────────────────────────────────┘
```

### Data flow — automated intake (the core value loop)
```
[every 300s] scheduler_service._loop
  → asyncio.to_thread(run_sync_cycle)
  → for each connected org:
      billing gate (email_automation?) → sync_gmail()
        → Gmail list "is:unread has:attachment"
        → filter PDF/PNG/JPG → dedupe on gmail_message_id
        → persist email_messages + email_attachments (status=pending)
      → process_pending()
        → per attachment: quota → download bytes → route:
             digital PDF → pypdf text → Gemini text
             scanned/image → Gemini vision
          → ExtractedInvoice validation/normalization
          → save_invoice (upsert) → status=completed + invoice_id
          → every step written to invoice_processing_logs
```

---

## 2. Code Quality Review

### Genuine strengths
- **Clean layering.** Route handlers are thin; business logic lives in `services/`. `main.py` contains no SQL and no AI calls.
- **HTTP-ignorant services.** Services return structured error codes (`unreadable_pdf`, `ai_unavailable`); the web layer maps them to status codes via `ERROR_STATUS`. Correct direction of dependency.
- **Queue-ready pipeline.** `process_attachment(id)` is a self-contained unit of work; `process_pending` is just a loop over it. Swapping in Celery is a genuine drop-in.
- **Boundary validation for AI output.** `ExtractedInvoice` coerces messy LLM output (comma strings, currency symbols, non-ISO dates) into typed values at one place.
- **Consistent, purposeful comments** explaining *why*, not *what*.
- **Portability seam.** `DATABASE_URL` and the dialect-agnostic get-or-create upsert show real forethought.

### Defects and debt

| # | Finding | Evidence | Severity |
|---|---|---|---|
| Q1 | **Zero automated tests.** No unit, integration, or E2E tests anywhere. | no `tests/` | **Critical** |
| Q2 | Session boilerplate (`db = SessionLocal(); try/finally: db.close()`) repeated ~25×. `get_db()` exists in `db.py` but **is never used** — services self-manage sessions, so FastAPI DI is bypassed. | `db.py:27` vs all services | High |
| Q3 | **Module-level side effects**: 5 DDL functions execute at import time in `main.py:95-99`. Importing the app mutates the database — makes unit testing nearly impossible. | `main.py:95` | High |
| Q4 | Dead code: `config.py` (0 bytes), `readers/ocr_reader.py` (0 bytes), `invoice.txt` (unreferenced). | verified unreferenced | Low |
| Q5 | Schema DDL is split between raw `sqlite3` (users/orgs/invoices) and `Base.metadata.create_all` (email tables) — two competing mechanisms. | `user_service.py` vs `email_service.py` | Medium |
| Q6 | `email_service._get_account_credentials` (underscore = private) is imported across module boundaries by `processing_service`. | `processing_service.py:22` | Low |
| Q7 | No custom exception hierarchy; `except Exception` used broadly in the pipeline, which will mask bugs (e.g. a `TypeError` looks like a download failure). | `processing_service.py:112,120` | Medium |
| Q8 | Frontend `build` script is `vite build` with no `tsc` gate — type errors cannot fail a build. | `frontend/package.json` | Medium |

---

## 3. Production Readiness Audit

| Area | Status | Evidence |
|---|---|---|
| Configuration | ⚠️ Scattered `os.getenv` across 5 modules; empty `config.py`; no schema/validation; **no fail-fast** if `JWT_SECRET`/`FERNET_KEY` missing | `auth_service.py:11`, `crypto_service.py:13` |
| Secrets | ✅ `.env` gitignored and **never committed** (verified across full history). OAuth tokens Fernet-encrypted at rest. ⚠️ No rotation strategy; no secret manager | `.gitignore`, `git log` |
| Logging | ⚠️ Basic `logging.basicConfig` INFO. Not structured/JSON, no correlation IDs, no request logging, no PII policy | `main.py:65` |
| Monitoring | ❌ None. No metrics, no APM, no error tracking (Sentry), no alerting | — |
| Health checks | ⚠️ `GET /` returns a static string — does **not** verify DB or dependencies. No `/readyz` | `main.py:220` |
| Background processing | ❌ **In-process loop. Breaks under horizontal scaling** — every instance runs the same cycle → duplicate AI spend and upsert races | `scheduler_service.py` |
| Graceful shutdown | ⚠️ `lifespan` cancels the task, but an in-flight sync cycle is killed mid-work; attachments can be left stuck in `processing` forever (no stale-job recovery) | `scheduler_service.py:stop` |
| Retry policy | ⚠️ Gemini 503 retried 3× with backoff. Nothing else retried (Gmail, DB). No dead-letter queue | `ai_service.py:150` |
| Deployment | ❌ No Dockerfile, no CI, no IaC, no environment separation | — |
| Rollback | ❌ None. Hand-rolled migrations are forward-only with no down-path | — |
| Horizontal scaling | ❌ Blocked by SQLite + in-process scheduler | — |
| Caching | ❌ None anywhere | — |

### Performance bottlenecks (concrete)
1. **No pagination** on `/invoices`, `/emails`, `/organization/members`, `/processing/jobs` — every row is serialized on every call. Dashboard loads the full invoice list *twice* (summary + list).
2. **Missing indexes** — live introspection shows exactly **one** real index (`idx_invoices_org_vendor_number`). `email_attachments` has **no index at all**, yet is queried by `org_id + status` on every pipeline run and every dashboard load.
3. **N+1 queries** — `list_email_messages` iterates `m.attachments` per message with no eager loading.
4. **Synchronous AI in the request path** — `/extract` blocks a worker for the full Gemini round-trip (seconds), plus `time.sleep` up to 6s on retries.
5. **Full-table count per quota check** — `count_invoices_this_month` runs a `COUNT(*)` with `LIKE 'YYYY-MM%'` on an unindexed text column, on *every* upload.

---

## 4. Security Audit

### Implemented correctly ✅
- **Password storage** — bcrypt with per-password salt (`gensalt()`), industry standard.
- **Session transport** — JWT in an **httpOnly** cookie; JavaScript cannot read it (XSS token theft mitigated). `SameSite=Lax` gives baseline CSRF protection.
- **Token at rest** — Gmail OAuth access/refresh tokens Fernet-encrypted; `get_email_account` never returns them.
- **OAuth CSRF** — `state` parameter generated with `secrets.token_urlsafe`, stored in an httpOnly cookie, and compared on callback.
- **Tenant isolation** — every data query filters on `org_id`; verified by test that a cross-org member operation returns 404.
- **Authorization** — `require_admin` enforced **server-side**; the invite code is stripped from API responses for members (`_me_payload`), not merely hidden in the UI.
- **User enumeration** — login returns an identical 401 for unknown-email and wrong-password.
- **SQL injection** — no raw string interpolation of user input; SQLAlchemy parameterizes, and raw DDL uses no user data.
- **Secrets in VCS** — none, ever.

### Vulnerabilities and gaps

| # | Issue | Detail | OWASP | Severity |
|---|---|---|---|---|
| S1 | **No rate limiting anywhere** | `/login` is freely brute-forceable; `/extract` allows unbounded AI cost abuse; no account lockout | A07 | **Critical** |
| S2 | **`secure=False` on auth cookie** | `main.py:290` — cookie transmitted over plaintext HTTP; trivial session theft off-HTTPS. Comment acknowledges "DEV ONLY" but it is not environment-driven | A02/A05 | **Critical** (on deploy) |
| S3 | **Memory-exhaustion DoS on upload** | `main.py:572-575` — `await file.read()` loads the **entire** body into RAM *before* the 10 MB check. A 2 GB POST is fully buffered first | A05 | **High** |
| S4 | **Prompt injection via invoice content** | `ai_service.extract_invoice` concatenates untrusted invoice text directly into the prompt. A supplier can email a PDF containing instructions that alter extracted values (e.g. redirect payment details) | LLM01 | **High** |
| S5 | **No attachment size limit in the email pipeline** | `MAX_FILE_SIZE` guards only `/extract`. `download_attachment` pulls arbitrary bytes into memory | A05 | High |
| S6 | **No token revocation** | Logout only clears the cookie; the JWT stays valid up to 60 min. No `jti` blocklist, no refresh-token rotation. A stolen token cannot be invalidated | A07 | High |
| S7 | **No CSRF tokens** | Relies solely on `SameSite=Lax`. State-changing `POST`/`PATCH`/`DELETE` have no anti-CSRF token | A01 | Medium |
| S8 | **No audit log for security events** | `invoice_processing_logs` covers AI processing only. Logins, failed logins, role changes, member removal, Gmail connect/disconnect are **not** recorded | A09 | High |
| S9 | **Fail-open on missing secrets** | `JWT_SECRET`/`FERNET_KEY` are read at import with no validation; misconfiguration surfaces as a runtime 500, not a boot failure | A05 | Medium |
| S10 | **CORS + API URL hardcoded** | `allow_origins=["http://localhost:5173"]` and `API_URL = "http://localhost:8000"` are literals — not environment-driven | A05 | Medium (blocks deploy) |
| S11 | **No security headers** | No HSTS, CSP, X-Frame-Options, X-Content-Type-Options middleware | A05 | Medium |
| S12 | **No password policy** | Only `min_length=8`. No complexity, no breach-list check, no rotation, no MFA | A07 | Medium |
| S13 | **PII in third-party prompts** | Full invoice contents (supplier names, amounts, addresses) are sent to Google Gemini with no DPA, redaction, or customer disclosure documented | GDPR | High (compliance) |

**Not applicable / not found:** No SSRF vector (no user-supplied URLs fetched). No path traversal (filenames from Gmail are never used as filesystem paths — `tempfile` generates names). XSS risk is low (React escapes by default; no `dangerouslySetInnerHTML` found).

---

## 5. AI System Review

| Dimension | Assessment |
|---|---|
| Prompt engineering | ⚠️ Single flat file (`prompts/invoice_prompt.txt`), 28 lines. Explicit rules (JSON only, null for missing, ISO dates, "never guess"). Reasonable but basic — no few-shot examples, no schema enforcement via `response_schema`. |
| Prompt management | ❌ No versioning, no A/B testing, no per-tenant customization, no changelog. |
| Model selection | ⚠️ `"gemini-flash-latest"` is a **hardcoded string literal**, not configurable. The `-latest` alias means **Google can change the model under you** with no code change and no regression detection. |
| Hallucination risk | ⚠️ **Partially mitigated.** JSON mode + `_extract_json` + `ExtractedInvoice` coercion. Business validation is minimal: only "has `invoice_number` OR `total`". **No arithmetic validation** (e.g. does GST + subtotal reconcile to total?), no vendor cross-checking. |
| Confidence scores | ❌ None. Every extraction is treated as equally trustworthy. |
| Human review workflow | ❌ **None.** Extracted values are written straight to the invoices table. There is no "needs review" state, no side-by-side original-vs-extracted UI, no correction capture. **This is the single biggest AI product gap** for a finance tool. |
| Retry strategy | ✅ 3 attempts with linear backoff on `ServerError`. ⚠️ `time.sleep` blocks a worker thread; no jitter; no retry on client/network errors. |
| Cost optimization | ⚠️ Good instinct: quota is checked *before* the AI call; text path preferred over vision when a text layer exists. ❌ But no token counting, no cost attribution per tenant, no budget cap, no caching of repeat documents. |
| AI monitoring | ❌ No token/latency/cost/error-rate metrics. |
| AI evaluation | ❌ **No eval set, no accuracy baseline, no regression tests.** There is no way to know whether a prompt or model change improves or degrades extraction. |
| Error handling | ✅ Structured error codes mapped to HTTP statuses; failures logged per-attachment. ⚠️ `_generate_invoice_json` catches only `ServerError` and parse errors — a `ClientError` (e.g. bad API key, model removed) propagates as an unhandled 500. |

**Verdict: the AI system is NOT production-ready for finance.** The blockers are, in order: (1) no human-in-the-loop review, (2) no accuracy measurement, (3) prompt-injection exposure, (4) unpinned model.

---

## 6. Database Review

**Schema:** 7 tables, sensible 3NF-ish normalization, correct relationship chain (`organizations → users / invoices / email_accounts → email_messages → email_attachments`), with `invoice_processing_logs` as an audit side-table.

| Issue | Detail | Severity |
|---|---|---|
| D1 | **Money stored as `REAL` (float).** `gst` and `total` are floating-point. Currency in binary floating point produces rounding errors that break financial reconciliation. Must be `NUMERIC`/`Decimal`. | **Critical** |
| D2 | **`created_at` is populated by a SQLite-only TRIGGER** (`invoices_set_created_at`). On Postgres this trigger will not exist → `created_at` stays NULL → `count_invoices_this_month` (which filters `created_at LIKE 'YYYY-MM%'`) returns **0** → **every tenant silently gets unlimited free usage.** A revenue-leaking latent bug in the planned migration. | **Critical** |
| D3 | **Missing indexes.** Live introspection: only `idx_invoices_org_vendor_number` exists. Needed: `email_attachments(org_id, status)`, `email_messages(org_id)`, `users(org_id)`, `invoice_processing_logs(org_id, attachment_id)`, `invoices(org_id, created_at)`. | High |
| D4 | **No migration framework.** Schema changes are hand-written `ALTER TABLE` blocks inside startup functions, guarded by `PRAGMA table_info` checks. Forward-only, no rollback, no history, not reviewable. | High |
| D5 | **SQLite in production.** Single-writer locking, no network access, ephemeral on most PaaS filesystems. | **Critical** |
| D6 | **Dates stored as TEXT.** Works via ISO lexical ordering but prevents date arithmetic and proper indexing. | Medium |
| D7 | **No FK cascade / referential cleanup.** Removing a member leaves `invoices.user_id` pointing at a deleted row. Deleting an org orphans everything. | Medium |
| D8 | **TOCTOU race in `save_invoice`.** Get-or-create is read-then-write with no transaction guard or `IntegrityError` handling; concurrent upload + auto-sync of the same invoice can raise an unhandled unique-constraint violation. | Medium |
| D9 | **No backup or restore strategy.** No documented procedure, no PITR, no tested restore. | **Critical** for paying customers |
| D10 | Multi-tenancy is **row-level via `org_id`** and consistently applied — but there is no defense-in-depth (no RLS, no automatic query filter). One forgotten `.filter(org_id=...)` leaks cross-tenant data. | Medium |

---

## 7. API Review

**28 routes**, all in `main.py`. Consistent naming, correct verb usage, thin handlers.

| Dimension | Assessment |
|---|---|
| REST standards | ✅ Good. Correct verbs, plural nouns, path params for identity. Meaningful status codes: 401/403/404/409/413/415/422/402/503. |
| Validation | ✅ Strong. Pydantic models with `EmailStr`, `Field(min_length=8)`, `Literal[...]` for enums — free 422s. |
| Error responses | ✅ Consistent `{"detail": "..."}` (FastAPI convention), handled uniformly by the frontend. |
| Pagination | ❌ **Absent everywhere.** Unbounded list endpoints. |
| Filtering/sorting | ⚠️ `/invoices` supports search + status + date range. Sorting is fixed (`id DESC`). No filtering on other collections. |
| Versioning | ❌ No `/v1` prefix. Any breaking change breaks all clients. |
| Documentation | ⚠️ Auto-generated OpenAPI at `/docs` (free from FastAPI). No descriptions, examples, or auth documentation. No published/pinned spec. |
| Consistency | ⚠️ Mostly good. Inconsistency: `/processing/run` and `/emails/sync` are workspace-wide operations available to **members**, while other workspace operations require admin. `/processing/run` also lacks the `email_automation` plan gate that `/emails/sync` has. |
| Idempotency | ⚠️ `save_invoice` upserts (good), but `POST /emails/sync` and `/processing/run` have no idempotency keys. |

---

## 8. Frontend Review

**9 pages, 6 shared components, 100% TypeScript, `tsc --noEmit` clean.**

| Dimension | Assessment |
|---|---|
| UX | ✅ Coherent MUI design system, sidebar+topbar shell, consistent theming, workspace/role chips, clear paywall messaging. |
| Accessibility | ⚠️ **Not audited.** Some `aria-label`s present (menu toggle, `aria-hidden` on decorative icons). No keyboard-navigation testing, no contrast verification, no screen-reader pass, `window.confirm` used for destructive actions. |
| Responsive | ✅ Genuine: MUI breakpoints throughout, permanent drawer → temporary drawer on mobile, `overflow-x` scroll wrappers on tables. |
| Performance | ⚠️ **No code splitting** — all 9 pages eagerly imported in `App.tsx`; single bundle. No memoization. Dashboard issues 2 API calls and re-fetches the entire invoice list. |
| Lazy loading | ❌ None. |
| State management | ⚠️ Local `useState` + prop drilling via `Outlet context`. Adequate at current size; no cache layer, so data is re-fetched on every navigation. No React Query/SWR. |
| Error states | ⚠️ Per-page `Alert`s and try/catch on fetches. ❌ **No error boundary** — a render error blanks the whole app. |
| Empty states | ✅ Genuinely good — dedicated `EmptyState` component with icon, message, and call-to-action, used consistently. |
| Loading states | ✅ Skeleton loaders (`Skeleton`, `SkeletonLines`) plus button-level pending text. |
| Component design | ✅ Small, typed, single-purpose, reusable. |
| Code organization | ✅ Clear `pages/` vs `components/`, shared `types.ts` mirroring API shapes, single `api.ts` client. |
| Config | ❌ `API_URL` hardcoded — **blocks any deployment**. |
| Testing | ❌ None. |

---

## 9. DevOps Review

**This is the weakest area of the entire product — effectively greenfield.**

| Item | Status |
|---|---|
| CI/CD | ❌ None |
| Containerization | ❌ No Dockerfile / compose |
| IaC | ❌ None |
| Environment separation | ❌ No dev/staging/prod distinction; single `.env` |
| Secrets management | ⚠️ Local `.env` only; no vault/manager; no rotation |
| Build pipeline | ⚠️ `vite build` exists but is not type-gated and not automated |
| Release strategy | ❌ None |
| Monitoring/observability | ❌ None |
| Disaster recovery | ❌ No backups, no RTO/RPO, no tested restore |
| Prior deploy attempt | ⚠️ A Vercel deployment exists (`invoice-ai-pink.vercel.app`) returning `FUNCTION_INVOCATION_FAILED` — consistent with deploying a stateful FastAPI+SQLite app to serverless |

---

## 10. SaaS Readiness

| Capability | Status |
|---|---|
| Multi-tenancy | ✅ Real. Org-scoped data, verified isolation, per-org unique invoice keys. |
| Team support | ✅ Invite codes, multi-user workspaces, member list. |
| Organization support | ✅ First-class tenant entity. |
| RBAC | ✅ admin/member with server-side enforcement and a last-admin invariant. |
| Usage tracking | ✅ Invoices/month metered per org. |
| Subscription readiness | ⚠️ Plan model, limits, and feature gating are built and enforced — **but no payment provider is integrated.** You cannot currently charge anyone. |
| Billing UI | ⚠️ Plan comparison + usage meter exist; the upgrade button is inert. |
| Feature flags | ⚠️ Only plan-based gating (`email_automation`). No general flag system. |
| Customer onboarding | ❌ No guided setup, no sample data, no empty-state tutorial, no email verification. |
| Admin/back-office | ❌ No internal admin panel to view tenants, adjust plans, or support customers. |
| Licensing/ToS | ❌ No LICENSE, ToS, or privacy policy in the repo. |

---

## 11. Enterprise Readiness

| Requirement | Status |
|---|---|
| RBAC | ⚠️ Two roles only; no granular permissions, no custom roles |
| Audit logs | ⚠️ AI processing only; **no auth/admin/data-access audit trail** |
| SSO (SAML/OIDC) | ❌ None |
| SCIM provisioning | ❌ None |
| API keys / programmatic access | ❌ None (cookie-only auth; no machine-to-machine path) |
| Outbound webhooks | ❌ None |
| ERP/accounting integrations | ❌ None (no QuickBooks/Xero/NetSuite/SAP) |
| GDPR | ❌ No data export, no right-to-erasure, no consent records, no DPA with subprocessors, no data-residency control |
| SOC 2 | ❌ No evidence of controls, policies, access reviews, or logging discipline |
| Data retention | ❌ No policy or enforcement |
| Backups | ❌ None |
| Encryption | ⚠️ OAuth tokens encrypted at rest; invoice data (financial PII) stored in plaintext; no TLS enforcement configured |

---

## 12. Competitive Analysis

**Category:** AI-powered Accounts Payable automation / invoice data capture.

**Leaders:** Bill.com, Tipalti, Stampli, AvidXchange, Ramp Bill Pay, Rossum, Vic.ai, Nanonets, Docsumo; adjacent: Dext, Hubdoc (bookkeeping capture).

| Capability | InvoiceAI | Market standard |
|---|---|---|
| AI extraction (digital + scanned) | ✅ | ✅ |
| Email intake automation | ✅ | ✅ |
| Multi-tenant workspaces + roles | ✅ | ✅ |
| Dashboard/reporting | ✅ basic | ✅ advanced |
| **Line-item extraction** | ❌ header only (vendor/number/date/GST/total) | ✅ table-level detail |
| **Human review / verification UI** | ❌ | ✅ **universal — this is the core UX of the category** |
| **Approval workflows** | ❌ | ✅ multi-step routing, delegation |
| **PO matching (2/3-way)** | ❌ | ✅ |
| **Accounting integrations** | ❌ | ✅ QuickBooks/Xero/NetSuite — table stakes |
| **Payment execution** | ❌ | ✅ ACH/card/international |
| Duplicate detection | ⚠️ exact (org+vendor+number) only | ✅ fuzzy + amount/date heuristics |
| Original document storage | ❌ **not retained** | ✅ archived + viewable |
| Audit trail | ⚠️ processing only | ✅ full financial audit trail |
| Supplier management | ⚠️ derived list only | ✅ master records, banking details |

**Honest positioning:** this is a competent **invoice data-capture tool**, not yet an **AP automation platform**. The gap to the category is approval workflows, accounting sync, and human verification.

**Real competitive advantages:** (1) modern LLM extraction handles messy layouts without per-template training that older OCR vendors require; (2) genuinely fast setup — connect Gmail and invoices flow in; (3) transparent low price vs enterprise-priced incumbents.

**Highest-impact features to add, in order:**
1. **Human review queue with confidence highlighting** — unlocks trust; every competitor has it.
2. **Store and display the original document** — you currently discard it; auditors require it.
3. **QuickBooks/Xero export or sync** — the #1 buying criterion for SMB finance.
4. **Line-item extraction** — needed for GL coding and PO matching.
5. **Approval workflow** — turns a capture tool into an AP product.

---

## 13. Business Review

**Who should buy:** SMB/mid-market finance teams (5–200 staff) drowning in 50–500 emailed supplier invoices/month, currently keying them manually; bookkeeping/accounting firms processing for multiple clients; India/APAC/Commonwealth businesses where GST capture matters.

**Who should NOT buy (today):** enterprises (no SSO/SOC 2/audit trail), regulated finance/healthcare (no compliance posture), companies needing payment execution or PO matching, anyone requiring on-prem/data residency.

**Best-fit industries:** professional services, agencies, e-commerce/retail, logistics, construction subcontractors, hospitality — high supplier-invoice volume, low process maturity.

**Biggest selling points:** zero-touch email intake; handles scanned/photographed invoices without template training; 10-minute setup; price point ~10× below incumbents.

**Biggest weaknesses:** no human review (finance teams will not blindly trust AI); no accounting integration (data ends in a silo); originals not retained; no approvals; unproven accuracy (no published benchmark).

**Pricing:** current $0/$29 is under-priced for the value and mis-metered. Recommended:
- **Starter $49/mo** — 100 invoices, 3 users
- **Growth $149/mo** — 500 invoices, unlimited users, accounting sync
- **Business $399/mo** — 2,000 invoices, approvals, API
- Overage ~$0.35–0.50/invoice. Anchor to labour saved (~$2–4 manual cost per invoice), not to AI cost.

**GTM:** (1) niche down to one vertical + one accounting platform (e.g. Xero-using agencies); (2) partner with bookkeeping firms as a channel — they bring dozens of clients each; (3) content SEO on "automate invoice data entry"; (4) offer a free accuracy audit — process 50 of a prospect's real invoices and show a measured accuracy report.

**Sales objections to expect:** "How accurate is it?" (you have **no measured answer** — fix this first); "Does it sync to QuickBooks?" (no); "Where does our data go?" (Google Gemini — needs a documented answer); "Who approves before payment?" (no workflow); "Is it SOC 2?" (no); "What if it extracts a wrong amount?" (no review step).

---

## 14. Testing Review

| Type | Status |
|---|---|
| Unit | ❌ None |
| Integration | ❌ None |
| E2E | ❌ None |
| Load | ❌ None |
| Security | ❌ None |
| **AI output/accuracy** | ❌ None — no labelled set, no baseline |
| Regression | ❌ None |
| Type checking | ✅ `tsc --noEmit` clean (frontend); ⚠️ not enforced in build, no Python type checker |

**Testing maturity: 0/5.** All verification to date has been manual. For a product that touches financial data and bills customers, this is the single largest engineering risk: no change can be made safely.

---

## 15. Launch Readiness Roadmap

### Phase 1 — Critical blockers before ANY deployment
1. Migrate SQLite → **Postgres** (managed, e.g. Neon/RDS)
2. **Fix the `created_at` trigger dependency** (move to an application/ORM default) — otherwise billing metering silently returns 0 on Postgres
3. Convert money columns to **`NUMERIC`/`Decimal`**
4. **Alembic** migrations, replacing hand-rolled `ALTER TABLE`
5. Environment-driven config: `API_URL`, CORS origins, `secure=True` cookies, fail-fast secret validation
6. **Rate limiting** on `/login`, `/register`, `/extract`
7. Fix streaming/size-limited upload handling (reject before buffering)
8. Dockerfile + a real deploy target (Render/Fly/ECS) + CI
9. Move the scheduler out-of-process (Celery/RQ + Redis, or a single designated worker) **before** running >1 instance
10. Backups with a **tested** restore

### Phase 2 — Required for first paying customers
11. **Stripe integration** (Checkout + signature-verified webhooks + portal) — you cannot charge today
12. **Human review queue** + confidence surfacing
13. **Store original documents** (S3/Blob) and display them
14. Test suite: unit + integration on auth, tenancy, billing, pipeline; AI accuracy eval set
15. Error tracking (Sentry) + uptime monitoring + real health checks
16. Security/audit logging for auth and admin actions
17. Pagination on all list endpoints + the missing indexes
18. ToS, privacy policy, subprocessor disclosure (Google Gemini)

### Phase 3 — Scale to 100 customers
19. Queue-based processing with retries + dead-letter handling; stale-job recovery
20. Accounting integration #1 (QuickBooks or Xero)
21. Line-item extraction
22. Approval workflows
23. Structured logging + metrics + dashboards; per-tenant AI cost attribution
24. Frontend code-splitting, caching layer (React Query), error boundaries
25. Email verification + password reset (neither exists today)

### Phase 4 — Scale to 1,000 customers
26. Read replicas / connection pooling; DB partitioning strategy
27. Multi-region or at least multi-AZ; autoscaling workers
28. Caching (Redis) for dashboards/aggregates
29. Self-serve onboarding, in-app support, admin back-office
30. Prompt versioning + continuous accuracy regression in CI
31. Fuzzy duplicate detection; supplier master records

### Phase 5 — Enterprise
32. SSO (SAML/OIDC) + SCIM
33. SOC 2 Type II programme; pen test
34. Full audit trail + data retention + legal hold
35. GDPR tooling (export, erasure, DPA, residency)
36. Public API + API keys + outbound webhooks
37. Granular/custom roles; approval matrices
38. SLA, status page, DR runbooks with tested RTO/RPO

---

## 16. Prioritized Action Plan

| # | Issue | Category | Priority | Business impact | Technical impact | Effort | Recommended solution |
|---|---|---|---|---|---|---|---|
| 1 | SQLite in production | Infra | **Critical** | Cannot serve concurrent customers; data loss on ephemeral FS | Blocks all scaling | 2–3 d | Managed Postgres via `DATABASE_URL`; verify all queries |
| 2 | `created_at` SQLite-trigger dependency | Data/Billing | **Critical** | **Silent revenue leak** — quota reads 0 on Postgres, everyone gets unlimited | Latent, invisible until migration | 2 h | ORM-level default / `server_default=func.now()` |
| 3 | Money as float | Data | **Critical** | Financial rounding errors; reconciliation disputes | Type migration needed | 1 d | `NUMERIC(12,2)` + Python `Decimal` |
| 4 | Zero tests | Quality | **Critical** | Every change risks breaking billing/tenancy | No safe refactoring | 5–8 d | pytest + httpx; cover auth, tenancy, billing, pipeline |
| 5 | No payment integration | Business | **Critical** | **No revenue possible** | — | 3–4 d | Stripe Checkout + verified webhooks + portal |
| 6 | No rate limiting | Security | **Critical** | Brute force; unbounded AI cost abuse | Trivial to exploit | 0.5 d | `slowapi`/Redis limits on auth + extract |
| 7 | `secure=False` cookies | Security | **Critical** on deploy | Session hijacking over HTTP | — | 1 h | Env-driven `secure`, force HTTPS, HSTS |
| 8 | In-process scheduler blocks scaling | Arch | **Critical** | Duplicate AI spend + races when scaled | Prevents >1 instance | 2–3 d | Celery/RQ + Redis, or single worker dyno |
| 9 | No human review workflow | Product/AI | **Critical** | Finance teams won't trust unreviewed AI; blocks adoption | New UI + state model | 4–5 d | Review queue, confidence flags, edit-before-commit |
| 10 | No backups | Ops | **Critical** | Total data loss = company-ending | — | 0.5 d | Managed PITR + **tested** restore runbook |
| 11 | Upload buffered before size check | Security | High | Memory-exhaustion DoS | Worker crashes | 2 h | Enforce limit via streaming/`Content-Length` |
| 12 | Prompt injection | AI/Security | High | Attacker-controlled extracted values → wrong payments | — | 1 d | Delimit/escape doc text, instruction hierarchy, output sanity checks |
| 13 | Missing indexes | Perf | High | Slow dashboards as data grows | Table scans | 2 h | Composite indexes on `org_id(+status/created_at)` |
| 14 | No pagination | Perf/API | High | Timeouts for large tenants | Unbounded payloads | 1 d | Cursor/limit-offset + frontend paging |
| 15 | No security audit log | Security/Ent | High | Cannot investigate incidents; blocks enterprise | — | 1–2 d | `audit_events` table for auth/admin/data access |
| 16 | Originals not retained | Product/Compliance | High | Auditors require source documents | Needs blob storage | 2 d | S3/Blob + signed-URL viewer |
| 17 | No AI accuracy measurement | AI | High | Cannot answer "how accurate?" — top sales objection | No regression safety | 2–3 d | Labelled eval set + scored CI run |
| 18 | No token revocation | Security | High | Stolen token valid up to 60 min | — | 1 d | Refresh tokens + `jti` blocklist |
| 19 | Hardcoded API URL / CORS | DevOps | High | Blocks deployment entirely | — | 2 h | `VITE_API_URL` + env CORS list |
| 20 | No CI/CD or Docker | DevOps | High | Manual, unrepeatable deploys | No rollback | 2 d | Dockerfile + GitHub Actions (lint→typecheck→test→deploy) |
| 21 | No error tracking/monitoring | Ops | High | Silent production failures | Blind operation | 0.5 d | Sentry + uptime + real health checks |
| 22 | No migration framework | Data | High | Unsafe schema evolution | No rollback | 1 d | Alembic + baseline migration |
| 23 | Model alias unpinned | AI | Medium | Google can change behaviour silently | Unpredictable output | 1 h | Pin explicit model version; config-driven |
| 24 | Session boilerplate / unused `get_db` | Quality | Medium | — | Duplication, untestable | 1 d | Adopt `Depends(get_db)` |
| 25 | Import-time DDL side effects | Quality | Medium | — | Blocks testing | 4 h | Move into lifespan/migrations |
| 26 | `save_invoice` TOCTOU race | Data | Medium | Rare failed imports | Unhandled IntegrityError | 3 h | Native upsert or catch+retry |
| 27 | No email verification / password reset | Product | Medium | Support burden; fake signups | — | 2 d | Token email flows |
| 28 | No error boundary / code splitting | Frontend | Medium | Blank screen on error; slow first load | — | 1 d | Error boundary + `React.lazy` |
| 29 | Dead files (`config.py`, `ocr_reader.py`, `invoice.txt`) | Quality | Low | — | Confusion | 15 m | Delete |
| 30 | No API versioning | API | Low→High later | Breaking changes hit clients | — | 2 h | `/v1` prefix now |

---

## 17. Final Assessment

### Scores

| Dimension | Score | Rationale |
|---|---|---|
| **Overall production readiness** | **42 / 100** | Feature-rich prototype; missing the operational, testing, and data-integrity foundation for paying customers |
| Architecture | 70 | Genuinely clean layering and a queue-ready pipeline; undermined by import-time side effects, no DI, in-process scheduler |
| Security | 52 | Strong fundamentals (bcrypt, httpOnly JWT, encrypted tokens, verified tenant isolation, server-side RBAC); no rate limiting, insecure cookie flag, no audit log, prompt injection |
| AI | 48 | Excellent output validation and cost-aware routing; no human review, no evals, no confidence, unpinned model |
| Code quality | 68 | Readable, consistent, well-commented, good separation; zero tests and duplicated session handling |
| Performance | 40 | One index, no pagination, no caching, sync AI in request path, N+1 |
| Scalability | 32 | SQLite + in-process scheduler are hard blockers to horizontal scaling |
| SaaS readiness | 62 | Real multi-tenancy, roles, plans, metering, gating — but cannot collect payment |
| Enterprise readiness | 22 | No SSO, audit trail, API keys, integrations, or compliance posture |
| UX | 70 | Cohesive MUI system, responsive, strong empty/loading states; no a11y audit, no error boundary |
| Maintainability | 58 | Clear structure and documentation, held back entirely by the absence of tests |

### Engineering effort remaining before a safe paid launch
**Approximately 6–9 weeks for one experienced full-stack engineer** (Phases 1–2): ~2–3 weeks infra/data hardening, ~1 week Stripe, ~1–1.5 weeks review workflow, ~1.5–2 weeks testing/observability, ~1 week security remediation.

### Highest technical risks
1. **Billing metering breaks silently on the Postgres migration** (the trigger dependency) — revenue leak that no test would catch today.
2. **Float money** corrupting financial accuracy irreversibly.
3. **Zero tests** — every fix risks regressing tenancy or billing.
4. **Scaling to 2 instances duplicates all email processing** (double AI spend, upsert races).
5. **No backups** — a single failure is unrecoverable.

### Highest business risks
1. **Cannot charge anyone** — no payment provider integrated.
2. **Unmeasured AI accuracy** — the #1 buyer question has no answer.
3. **No human review** — finance teams will not trust unverified automation.
4. **No accounting integration** — data dead-ends, limiting willingness to pay.
5. **PII sent to a third-party LLM** with no documented DPA/disclosure — a GDPR/procurement blocker.

### Missing capabilities (summary)
Payments · human review · original document storage · line items · approvals · accounting sync · SSO · API keys · webhooks · audit trail · backups · tests · CI/CD · monitoring · pagination · email verification · password reset.

### Would I recommend launching today?

**No — not for paying customers.**

To be precise about *why*: this is a genuinely impressive build with real architectural merit — clean service boundaries, working multi-tenancy, verified authorization, a functioning end-to-end AI pipeline, and thoughtful cost controls. It is far past "demo". But three things independently block a paid launch: **you cannot collect payment**, **you cannot recover from data loss**, and **you cannot verify that a change hasn't broken billing or tenant isolation**. Any one of those is disqualifying for handling customers' financial data.

**Recommended path:** complete Phase 1 + Phase 2 (~6–9 weeks), then run a **design-partner pilot** with 3–5 friendly customers on a free/discounted tier while you gather the accuracy data and review-workflow feedback that the product needs before it can be sold at scale.

---

## 18. Recommended Execution Order

**Sprint 1 — Data foundation (must precede everything)**
1. Alembic + baseline migration · 2. Postgres migration · 3. Fix `created_at` default (verify billing metering) · 4. Money → `Decimal` · 5. Add indexes · 6. Backups + tested restore

**Sprint 2 — Make it deployable and safe**
7. Env-driven config + fail-fast secrets · 8. `secure=True` cookies + HTTPS + security headers · 9. Rate limiting · 10. Streaming upload limits · 11. Dockerfile + CI · 12. Sentry + health checks

**Sprint 3 — Make it testable**
13. Move DDL out of import path · 14. Adopt `Depends(get_db)` · 15. pytest suite (auth, tenancy, billing, pipeline) · 16. AI accuracy eval set · 17. Delete dead files

**Sprint 4 — Make it chargeable**
18. Stripe Checkout · 19. Signature-verified webhooks · 20. Billing portal · 21. Plan-change/dunning edge cases

**Sprint 5 — Make it trustworthy**
22. Human review queue + confidence · 23. Store/display originals · 24. Security audit log · 25. Prompt-injection hardening · 26. Pin the model

**Sprint 6 — Make it scale**
27. Celery/Redis queue + retries + stale-job recovery · 28. Pagination everywhere · 29. Frontend splitting/caching/error boundary · 30. Structured logging + per-tenant AI cost metrics

**Then:** accounting integration → line items → approvals → enterprise (SSO, SOC 2, API).

---

*Evidence gaps: no production environment, load data, customer feedback, or accuracy benchmarks exist to review. Deployment target, expected tenant scale, and target market geography were not specified and would refine several recommendations above.*
