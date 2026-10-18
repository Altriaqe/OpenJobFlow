# OpenJobFlow Architecture

> System architecture for the public OpenJobFlow repository: component boundaries, data flow, interface contracts, failure semantics, and deployment topology.
>
> Status: reflects the code, migrations, tests, and Compose definitions on `main` at baseline `46c3835` (2026-10-18). Update this file when a boundary, interface, or failure rule changes; keep it free of credentials, server addresses, private paths, and real data.

| Document | Purpose |
| --- | --- |
| **ARCHITECTURE.md** (this file) | One-page architecture entry: layers, contracts, failure model, verification |
| [docs/architecture.md](docs/architecture.md) | Detailed Chinese architecture and operating boundaries |
| [docs/project-handoff.md](docs/project-handoff.md) | Current verified state, unfinished work, new-conversation entry |
| [docs/guides/ubuntu-deployment.md](docs/guides/ubuntu-deployment.md) | Self-hosted deployment, daily task, recovery |
| [README.md](README.md) | Public onboarding, Quick Start, configuration |

**Contents:** [1. Scope](#1-what-openjobflow-is) · [2. Context](#2-system-context) · [3. Layers](#3-layered-architecture) · [4. Data flow](#4-data-flow) · [5. Data model](#5-data-architecture) · [6. Failure model](#6-failure-model) · [7. Security](#7-security-and-privacy) · [8. Deployment](#8-deployment-topology) · [9. Verification](#9-verification-and-quality-gates) · [10. Limitations](#10-known-limitations) · [11. Change checklist](#11-change-checklist)

---

## 1. What OpenJobFlow is

OpenJobFlow is a self-hosted recruitment-data pipeline. It turns a **compliant, user-supplied JSON snapshot** into layered PostgreSQL data, fixed read-only analytics, deterministic briefs and charts, and optional external delivery to Telegram and a WeChat Official Account draft box.

It is deliberately not a general-purpose or enterprise data platform: no multi-tenancy, permission center, data catalog, scheduler UI, HA topology, or automatic recovery of expired upstream logins.

### 1.1 Design goals

1. **Replaceable source, stable core** — adapters translate source payloads; storage and analytics never depend on one website's response shape.
2. **One batch, one transaction** — a batch is committed completely or rolled back, and the batch row records the outcome.
3. **Read-only public analytics** — public endpoints execute fixed whitelisted SQL only; no arbitrary SQL, no AI-generated SQL.
4. **Independent delivery boundaries** — ETL, Telegram, and WeChat fail independently; no channel can roll back another.
5. **No blind retries** — an external request with an unknown result stops the pipeline and requires an operator check first.
6. **Secrets stay local** — credentials, cookies, browser profiles, proxy subscriptions, and real snapshots live only in the deployment environment.

### 1.2 Non-goals

- Bypassing a platform's login, CAPTCHA, rate limits, risk controls, or access restrictions.
- Automatically publishing to WeChat — only a reviewable draft is created.
- Claiming high availability, unattended long-term stability, or automatic upstream session recovery.
- Shipping real recruitment data, account identifiers, or server configuration in this repository.

---

## 2. System context

```text
                      deployment environment (private)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                                                                          │
  │  systemd timer                                                           │
  │      │                                                                   │
  │      ▼                                                                   │
  │  ops/daily_update.sh  ── flock ──►  one run at a time                    │
  │      │                                                                   │
  │      ├── API readiness probe (/ready)                                    │
  │      ├── snapshot existence probe (/reports/daily/status)                │
  │      ├── optional external collector (authorized, operator-owned)        │
  │      │        └── writes data/raw/inbox/*.json (never committed)         │
  │      ├── ETL run (python -m jobflow.cli)                                 │
  │      ├── Telegram brief  ┐                                               │
  │      └── WeChat article  ┴─ parallel, independent exit statuses          │
  │              └── WeChat draft create ──► manual review and publish       │
  │                                                                          │
  │  PostgreSQL (loopback) ◄── FastAPI (loopback by default) ◄── operator UI │
  └──────────────────────────────────────────────────────────────────────────┘
              │                                   │
              ▼                                   ▼
     Telegram Bot API                 WeChat Official Account APIs
     (operator's bot/chat)            (material upload + draft add)
```

**Trust boundaries**

| Boundary | Inside | Outside |
| --- | --- | --- |
| Data source | Snapshot contract and adapter tests | Authorized collector, platform terms, login state |
| Runtime | ETL, schema, API, report logic | Bot/account APIs, upstream recruitment sites |
| Secrets | Variable names and `.env.example` placeholders | `.env` values, tokens, cookies, profiles, subscriptions |
| Publication | Draft creation in the target account | Operator review and formal publish |

---

## 3. Layered architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Entry points                                                          │
│  systemd timer → ops/daily_update.sh      operator → React console    │
│  CLI: python -m jobflow.cli               operator → Streamlit (opt.)  │
└───────────────┬───────────────────────────────────────┬───────────────┘
                │ HTTP (bearer / session cookie)        │ SQL
                ▼                                       ▼
┌──────────────────────────────┐        ┌───────────────────────────────┐
│ API layer  src/jobflow/api/  │        │ Storage layer  src/jobflow/db/ │
│  health, analytics, reports, │◄──────►│  connection, batches, jobs,    │
│  operations, auth, stages    │        │  raw_jobs, snapshots,          │
│  FastAPI + Uvicorn           │        │  deliveries, drafts, analytics │
└──────────────┬───────────────┘        └──────────────┬────────────────┘
               │ orchestration                         │ psycopg 3
               ▼                                       ▼
┌──────────────────────────────┐        ┌───────────────────────────────┐
│ Report and ETL services      │        │ PostgreSQL                    │
│  reports/ daily, multi,      │        │  ops    run and delivery state│
│  wechat article/draft, chart │        │  raw    source payload        │
│  workers/ batch transaction  │        │  core   standardized jobs     │
│  adapters/ validate, map     │        │  mart   fixed aggregate views │
│  channels/ telegram, wechat  │        └───────────────────────────────┘
│  operations/ probes, checks  │
└──────────────────────────────┘
```

Dependency rule: `api → reports/operations → channels/db → models/adapters`. The adapter converts source shape; the worker owns the transaction; the database module owns SQL. Channels never write ETL data, and the AI layer never touches PostgreSQL.

### 3.1 Module map

| Path | Responsibility | Does not |
| --- | --- | --- |
| `src/jobflow/adapters/` | Validate snapshot fields, map source shape, normalize salary/city/skills | Write to the database, decide batch outcomes |
| `src/jobflow/collectors/` | Minimal HTTP collection example | Provide the production browser collector |
| `src/jobflow/models/` | `JobRecord` and `SnapshotMetadata` value types | I/O |
| `src/jobflow/workers/` | Batch orchestration, commit/rollback, batch status | Render reports, send messages |
| `src/jobflow/db/` | Parameterized SQL for `ops/raw/core/mart`, connections | Business rules or HTTP calls |
| `src/jobflow/api/` | Health, analytics, reports, operations, auth, stage routes | Unbounded queries |
| `src/jobflow/reports/` | Query brief, comparison, charts, article package, draft flow, delivery state | Publish to WeChat |
| `src/jobflow/channels/` | Telegram and WeChat transports | Decide retry policy on uncertain results |
| `src/jobflow/operations/` | Run probes, checks, delivery workbench, manual capture | Change historical delivery records |
| `src/jobflow/ai/` | OpenAI-compatible summary over fixed metrics | Execute SQL or read raw records |
| `src/jobflow/dashboard/` | Optional Streamlit view | Serve as the public API |
| `migrations/` | Ordered schema evolution, `001`–`012` | Application logic |
| `ops/` | Daily shell orchestration and example units | Duplicate business rules in shell |
| `frontend/` | React/Vite operations console (optional) | Talk to PostgreSQL directly |

---

## 4. Data flow

### 4.1 Ingestion and transaction boundary

```text
snapshot JSON ──► adapter validation ──► normalized JobRecord list
                                              │
                                              ▼
                       workers/jobs.run_job_batch(connection)
                        │
                        ├─ 1. start_batch()                    commit   ← batch intent is durable
                        ├─ 2. insert_raw_jobs()   raw.job_records      ┐
                        ├─ 3. insert_jobs()       core.jobs (upsert)   ├─ one transaction
                        ├─ 4. insert_snapshot()   core.job_snapshots   │
                        └─ 5. finish_batch()      ops.batches          ┘ commit
                                              │
                    failure  ─────────────► rollback step 2–5
                                              └─ fail_batch() commit (error preserved)
```

Consequences:

- a failed import leaves no partial `raw`/`core`/snapshot data;
- the `ops.batches` row survives the rollback and records the error, so a failure is auditable;
- re-importing the same standardized records is idempotent by upsert, not by deletion;
- validation happens before any write, so a malformed snapshot stops the pipeline without touching business tables.

### 4.2 Daily orchestration (`ops/daily_update.sh`)

```text
1. flock                     single instance; a concurrent run exits without work
2. wait for /ready           bounded retries; stop if the API stays unready
3. snapshot probe            exists → skip capture for that keyword; 404 → capture;
                             any other result → stop (unknown state is never treated as absent)
4. optional collector        operator-owned; writes JSON into the inbox
5. ETL per batch             snapshot date, keyword, city scope, pages recorded in ops
6. capture-only mode         stop here when JOBFLOW_CAPTURE_ONLY=true
7. Telegram brief  ┐         started in parallel, exit status collected separately
   WeChat article  ┘
8. WeChat draft              only if the article stage succeeded
9. aggregate exit            any failed stage fails the service visibly
```

The shell owns **order and stop rules**; idempotency and delivery state live in the API and database. A nonzero exit is the signal an operator or systemd sees — the pipeline never reports success while a required stage failed.

### 4.3 Request paths

```text
GET  /health, /ready                            liveness / database readiness
GET  /analytics/cities|salaries/cities|skills   fixed SQL, read-only
GET  /operations/checks|runs|stages             operational history and stage state
POST /operations/checks/run                     admin session, explicit probe run
POST /auth/login                                exchange admin token for a session cookie
GET  /auth/session, POST /auth/logout           session check / sign out
GET  /dashboard/workbench|deliveries|summary    operator console data
POST /reports/cities/send                       report token, deterministic or AI brief
GET  /reports/daily/status                      report token, snapshot/delivery state
POST /reports/daily/send                        report token, daily brief delivery
GET  /reports/daily/multi/status                report token, multi-keyword delivery state
POST /reports/daily/multi/send                  report token, multi-keyword Telegram brief
POST /reports/daily/multi/recover               report token, confirm both text and photo missing
POST /reports/daily/multi/recover-photo         report token, confirm text visible, photo only
GET  /reports/daily/multi/wechat/status         report token, WeChat channel state
POST /reports/daily/multi/wechat/send           report token, optional template summary
POST /reports/daily/multi/wechat/resend         report token, confirm not received, then reclaim
POST /reports/daily/multi/wechat/article/generate  report token, local article package
GET  /reports/daily/multi/wechat/article/status report token, package status, no file paths
POST /reports/daily/multi/wechat/draft/create   report token, guarded draft creation
GET  /reports/daily/multi/wechat/draft/status   report token, date, status, safe error code
```

**Delivery guard** — before a Telegram or WeChat action, `operations/delivery_workbench.py` checks the date (no future dates), snapshot availability, article availability for WeChat, and the channel's current state. `sent`, `created`, `sending`, and `creating` cannot be claimed again; `uncertain` requires an explicit confirmation flag. Ambiguous requests therefore fail closed with `409` instead of sending a duplicate.

Two credentials, two purposes:

| Credential | Used by | Behaviour |
| --- | --- | --- |
| `REPORT_TRIGGER_TOKEN` | automation and protected endpoints | bearer token compared server-side; a valid admin session is also accepted |
| `JOBFLOW_ADMIN_TOKEN` (falls back to the report token) | operations console | exchanged for an 8-hour HMAC-signed, HttpOnly, SameSite=Strict session cookie |

Secrets are only compared server-side; the browser holds the signed session, not the secret.

---

## 5. Data architecture

### 5.1 Schema responsibilities

| Schema | Objects | Rule |
| --- | --- | --- |
| `ops` | `batches`, `report_deliveries`, `report_channel_deliveries`, `wechat_draft_jobs`, `platform_operation_runs`, `platform_check_results`, `platform_delivery_actions` | Append or update run/delivery state; never store secrets |
| `raw` | `job_records` | Preserve the source payload for traceability |
| `core` | `jobs`, `job_snapshots`, `job_snapshot_items` | Standardized, upserted, check-constrained |
| `mart` | `city_job_counts`, `city_salary_stats`, `skill_job_counts` | Views only; fixed aggregate queries for the API |

### 5.2 Migrations `001`–`012`

| # | Adds |
| --- | --- |
| 001 | `core.jobs` |
| 002 | `ops.batches` |
| 003 | `raw.job_records` |
| 004 | `mart.city_job_counts` |
| 005 | salary and skill analytics views |
| 006 | daily snapshots, snapshot items, initial delivery table |
| 007 | uncertain/partial delivery states and state consistency constraints |
| 008 | CNY monthly salary normalization in the salary view |
| 009 | per-channel delivery records |
| 010 | idempotent WeChat draft state per date |
| 011 | platform operation runs, check results, delivery actions |
| 012 | weekly salary unit and salary consistency constraints |

**Current limitation (not a completed feature):** the Compose `migrate` service replays every `*.sql` file in order and does not record applied versions. Files are written to be re-runnable (`IF NOT EXISTS`, `DROP … IF EXISTS` before `ADD CONSTRAINT`), but version-tracked incremental upgrade and a rollback strategy are still open work. Treat the migration path as initialization-safe, not as a versioned upgrade system. The project is in a stabilization and observation phase, so this upgrade path is intentionally deferred rather than in progress.

### 5.3 Delivery state

- `ops.report_deliveries` distinguishes pending, sending, sent, failed, uncertain, and partial states per message and photo.
- `ops.report_channel_deliveries` keeps Telegram and WeChat outcomes separate, so one channel's success never implies the other's.
- `ops.wechat_draft_jobs` records one idempotent draft state per date and a safe stage error code.
- An **uncertain** state is a stop condition, not a retry trigger: the operator checks the real channel first, then uses an explicit recovery endpoint.

---

## 6. Failure model

| Stage | Success | Failure handling | Never |
| --- | --- | --- | --- |
| Snapshot validation | Input satisfies the contract | Stop before any business write | Write partial raw data |
| ETL | Batch, raw, core, snapshot committed | Roll back, record failed batch | Leave half-applied business rows |
| API readiness | `/ready` returns ready | Daily task stops | Proceed on a possibly disconnected database |
| Snapshot probe | Known present or known absent (404) | Unknown result stops the run | Treat an unknown probe as "missing" |
| Report generation | Deterministic brief, chart, or article package | Keep the committed ETL, stop the dependent channel | Fabricate a report |
| Telegram | Text and photo each have an explicit state | Record failed/uncertain, stop for manual check | Auto-resend an uncertain request |
| WeChat article | Package generated locally | Keep ETL/Telegram, stop the draft stage | Pretend the package exists |
| WeChat draft | Draft created in the target account | Keep ETL/Telegram/article; fail the service visibly | Roll back data, auto-publish, auto-retry |
| Formal publish | Operator reviews and publishes | Outside the system | Automate publication |

Design invariants:

1. A committed ETL transaction is never undone by a channel failure.
2. Each channel reports its own outcome; no cross-channel inference.
3. Unknown external state stops automation and is surfaced, not guessed.
4. Failures are recorded with a stage and a safe error code, never with credentials or raw third-party responses.

---

## 7. Security and privacy

- **Secrets** — `.env`, bot tokens, chat IDs, app secrets, report tokens, cookies, browser profiles, private keys, proxy subscriptions, and real snapshots stay outside Git; `.gitignore` covers local runtime, logs, inbox data, virtualenvs, and private agent directories.
- **Public text guard** — `tests/docs/test_public_assets.py` scans tracked and untracked-but-not-ignored text for private network addresses, Windows absolute paths, literal Unix home paths, authenticated URLs, private keys, and known secret formats. Committed private material therefore fails CI-visible tests instead of silently leaking.
- **Placeholders** — public docs use `<SERVER_IP>`, `<JOBFLOW_DIR>`, `<SSH_USER>`, `<LAN_CIDR>`, `<PROXY_HOST>`, and similar tokens only.
- **Network exposure** — PostgreSQL binds to `127.0.0.1`; the API binds to loopback by default and is exposed only by deliberate operator configuration; analytics endpoints return aggregates only.
- **Least data** — the AI layer receives fixed structured metrics, not database access or raw records.
- **Drafts, not publishing** — the WeChat path stops at a reviewable draft; formal publishing stays manual.
- **Synthetic sample** — `examples/jobs.sample.json` is fully synthetic, with `example.com` links and no copied platform content.

---

## 8. Deployment topology

```text
Docker Compose (compose.yaml)
├── postgres    postgres:18-alpine, loopback port, named volume, healthcheck
├── migrate     one-shot psql loop over migrations/ (profile: tools)
├── etl         one-shot python -m jobflow.cli (profile: tools)
├── api         uvicorn jobflow.api.app:app, healthcheck, loopback by default
├── frontend    optional React/Vite console behind nginx (loopback)
└── dashboard   optional Streamlit view (profile: dashboard, loopback)

compose.proxy.yaml   adds an optional operator-managed egress proxy
                     (application egress only; not a Docker daemon pull proxy)
```

- The `etl` and `api` services share the `jobflow-app:local` image built from the current source tree.
- `runtime/` is mounted into the API container for generated article packages; it is git-ignored.
- `ops/*.service.example` are illustrative units only; the repository does not ship installable systemd units.
- The advanced browser collector is an independent project and is not distributed here.

Runtime expectation: single-host, single-operator, manually recoverable. It is not an HA or multi-tenant deployment.

---

## 9. Verification and quality gates

```bash
python -m pip install -e ".[dev]"     # Python 3.12
pytest -q                             # unit, contract, API, ops, docs, integration
ruff check .                          # static checks
ruff format --check .                 # formatting
docker compose config --quiet         # deployment file validity
```

- PostgreSQL integration tests need a reachable test database configured through the local environment; they are not run against production.
- Documentation tests enforce the public onboarding contract, local link resolution, directory structure, and the secret/private-path scan.
- A feature counts as done only when code, tests, and real run evidence agree; plans and roadmap items are not evidence.

---

## 10. Known limitations

1. Migration execution is replay-based; version tracking and rollback are unfinished. Versioned upgrades are deliberately deferred while the project is in a stabilization and observation phase.
2. No built-in backup/restore drill, monitoring, or alerting stack.
3. Upstream login expiry requires manual recovery; there is no notification or controlled auto-resume.
4. Long-running, reboot, and abnormal-delivery acceptance evidence is still being collected.
5. The architecture describes a single-host deployment; scaling, HA, and multi-tenant isolation are out of scope.
6. The React console and Streamlit dashboard are optional components, verified per deployment rather than guaranteed.

---

## 11. Change checklist

When a change touches architecture, update in the same change:

1. this file, for boundaries, contracts, failure rules, or topology changes;
2. [docs/architecture.md](docs/architecture.md), for the detailed Chinese description;
3. the relevant run guide under `docs/guides/` when commands or recovery steps change;
4. tests under `tests/docs/` when the public documentation contract changes;
5. [docs/project-handoff.md](docs/project-handoff.md) at the end of a session.

Run `git diff --check`, `pytest tests/docs -q`, and the tests relevant to the touched layer. Do not put credentials, server addresses, private paths, or real data into any public document.
