# Salary and Skill Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the BOSS snapshot ETL, PostgreSQL warehouse, and FastAPI API with traceable salary normalization and skill analytics.

**Architecture:** The BOSS adapter parses source strings into an expanded `JobRecord`; raw payloads remain unchanged while `core.jobs` stores normalized salary fields and a PostgreSQL skill array. Two ordinary mart Views expose fixed aggregates, and the existing analytics router serves them through bounded read-only endpoints.

**Tech Stack:** Python 3.12, dataclasses, pytest, PostgreSQL 16, psycopg 3, FastAPI

## Global Constraints

- Monthly salaries and daily salaries must never be combined.
- Skill analytics use only the BOSS `skills` field.
- Preserve `salary_text` for traceability.
- Do not infer experience, education, description, or publication time.
- Do not modify or submit the real snapshot or secrets.
- Existing uncommitted AI/report changes are out of scope and must be preserved.
- Do not commit or push without explicit user authorization.

---

### Task 1: Salary and skill normalization

**Files:**
- Modify: `src/jobflow/models/job.py`
- Modify: `src/jobflow/adapters/boss.py`
- Modify: `tests/adapters/test_boss.py`

**Interfaces:**
- Produces: `Salary(source_text, minimum, maximum, unit, months)`
- Produces: `parse_salary(value: str) -> Salary`
- Produces: `parse_skills(value: str) -> list[str]`
- Extends: `JobRecord` with salary and skill fields

- [ ] Add failing tests for `N-NK`, `N-NK·N薪`, `N-N元/天`, invalid salary, skill splitting, stable de-duplication, and complete BOSS mapping.
- [ ] Run `conda run -n jobflow pytest tests/adapters/test_boss.py -q` and confirm failures identify missing interfaces.
- [ ] Implement strict full-string salary parsing and ordered skill normalization.
- [ ] Require `salary` and `skills` in loaded snapshot records while allowing empty `skills`.
- [ ] Re-run adapter tests and confirm they pass.

### Task 2: Core persistence and migration

**Files:**
- Modify: `src/jobflow/db/jobs.py`
- Modify: `tests/db/test_jobs.py`
- Create: `migrations/005_add_salary_skill_analytics.sql`

**Interfaces:**
- Consumes: expanded `JobRecord`
- Produces: idempotent Upsert of salary fields and `skills TEXT[]`
- Produces: `mart.city_salary_stats` and `mart.skill_job_counts`

- [ ] Extend SQL tests to require all new parameters and content-change predicates.
- [ ] Update `insert_job()` so salary and skill changes update `updated_at`.
- [ ] Add an idempotent migration with nullable legacy salary columns, empty-array skill default, named check constraints, and both Views.
- [ ] Run `conda run -n jobflow pytest tests/db/test_jobs.py -q`.
- [ ] Apply migrations 001-005 to local PostgreSQL in filename order.

### Task 3: Fixed analytics queries

**Files:**
- Modify: `src/jobflow/db/analytics.py`
- Create: `tests/db/test_analytics.py`

**Interfaces:**
- Produces: `list_city_salary_stats(connection, limit)`
- Produces: `list_skill_job_counts(connection, limit)`

- [ ] Add failing query tests for SQL target, deterministic ordering, limit parameters, and result mapping.
- [ ] Implement both parameterized read-only query functions.
- [ ] Run `conda run -n jobflow pytest tests/db/test_analytics.py -q`.

### Task 4: FastAPI endpoints

**Files:**
- Modify: `src/jobflow/api/analytics.py`
- Modify: `tests/api/test_analytics.py`

**Interfaces:**
- Produces: `GET /analytics/salaries/cities?limit=20`
- Produces: `GET /analytics/skills?limit=20`

- [ ] Add endpoint tests for successful rows, default limit, empty lists, invalid bounds, and hidden database failures.
- [ ] Add both routes using the existing connection dependency and common `503` boundary.
- [ ] Run `conda run -n jobflow pytest tests/api/test_analytics.py -q`.

### Task 5: Real PostgreSQL and regression acceptance

**Files:**
- Modify: `tests/integration/test_postgres_connection.py`

**Interfaces:**
- Verifies: migration columns and constraints
- Verifies: normalized Upsert and `updated_at` semantics
- Verifies: daily salary exclusion and skill expansion
- Verifies: both endpoints against real PostgreSQL

- [ ] Add isolated integration rows with unique sources/cities/skills.
- [ ] Verify salary/skill storage, constraint rejection, both Views, and both APIs.
- [ ] Run `conda run -n jobflow pytest tests/integration/test_postgres_connection.py -q` with the configured local database.
- [ ] Run `conda run -n jobflow pytest -q`.
- [ ] Run `conda run -n jobflow ruff check .` and `conda run -n jobflow ruff format --check .`.
- [ ] Run `git diff --check` and confirm the real snapshot and secrets remain outside Git.
