# JobFlow Platform Operations Dashboard Implementation Plan

**Goal:** Build a localhost-only Streamlit operations console that reports the eight platform stages and safely records server checks, post-restart recovery runs, and date-selected Telegram/WeChat actions.

**Architecture:** Streamlit is a thin UI. A dashboard service layer owns stage-state calculation, fixed server probes, recovery orchestration, and channel actions; PostgreSQL stores checks and actions. Existing ETL, report, Telegram, and WeChat services remain the business implementation.

**Tech Stack:** Python 3.12, Streamlit, PostgreSQL, existing FastAPI/report/channel services, YAML stage configuration, pytest, Docker Compose, Ubuntu systemd.

## Global Constraints

- Use the public OpenJobFlow checkout for daily development; the historical private checkout is not a development source.
- Bind Streamlit to `127.0.0.1` and access it through the existing SSH tunnel.
- Use one administrator Token; do not add viewer roles or user management.
- Use the eight approved stages and six approved Chinese states from the design.
- Keep stage definitions in one versioned configuration file and runtime evidence in PostgreSQL.
- Require an explicit `report_date` for independent Telegram and WeChat actions.
- WeChat creates a draft only; final publication remains manual.
- Never automatically retry uncertain external results.
- Keep real credentials and private server values outside Git and the knowledge vault.

## Task 1: Configuration and Schema

Create `config/platform_stages.yaml`, `migrations/011_create_platform_operations.sql`, `src/jobflow/operations/models.py`, `src/jobflow/db/operations.py`, and focused tests. Define typed stage, check, operation, and delivery values. Add parameterized PostgreSQL tables for operation runs, individual check results, and date/channel/action-idempotent delivery actions. Verify exactly eight stages and invalid values in tests.

## Task 2: Stage-State Calculation

Create `src/jobflow/operations/stages.py` and tests. Expose `derive_stage_state()` and `build_stage_snapshot()`. Use precedence `异常 > 观察中 > 已验收 > 已完成 > 未开始`, and keep the calculation independent of SQL and Streamlit.

## Task 3: Server Checks and Recovery

Create `src/jobflow/operations/checks.py` and `src/jobflow/operations/runs.py` with tests. Expose `run_server_checks()` and `run_recovery()`. Use an allowlisted probe registry, redact exception details, block recovery after any failed check, stop after ETL failure, and record Telegram and WeChat outcomes independently without automatic retry.

## Task 4: Manual Deliveries

Create `src/jobflow/operations/deliveries.py` and tests. Expose `manual_telegram_delivery(report_date, admin_token, sender)` and `manual_wechat_draft(report_date, admin_token, sender)`. Validate the administrator Token and explicit date, preserve date forwarding, use idempotency records, and call only the existing WeChat draft path.

## Task 5: Streamlit Console

Modify `pyproject.toml`; create `src/jobflow/dashboard/app.py` and dashboard contract tests. Render platform overview, operations, and deliveries. Keep SQL, shell construction, and external HTTP out of the UI. Require a date before either channel action and disable actions for matching running or uncertain records.

## Task 6: Ubuntu Deployment and Documentation

Create `ops/jobflow-dashboard.service.example`, update Compose and the existing deployment/handoff docs, run migration 011, start Streamlit on localhost, and verify access through the existing tunnel. Perform one controlled read-only check and one user-selected recovery acceptance. Finish with tests, `git diff --check`, public-secret scans, and Markdown checks. Do not commit or push without authorization.

## Final Acceptance

The console must show eight derived stages, independently record all requested checks, block recovery after failed checks, record ETL/Telegram/WeChat steps independently, require an explicit date, prevent duplicate same-date/channel actions, avoid automatic uncertain retries, create but never publish WeChat drafts, remain localhost-only, and require the administrator Token.
