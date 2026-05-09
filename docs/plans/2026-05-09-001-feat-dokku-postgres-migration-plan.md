---
title: Dokku Deployment & PostgreSQL Migration
type: feat
status: completed
date: 2026-05-09
origin: docs/brainstorms/2026-05-09-dokku-postgres-migration-requirements.md
deepened: 2026-05-09
---

# Dokku Deployment & PostgreSQL Migration

## Overview

The application will transition from using raw `sqlite3` queries to SQLAlchemy ORM, and deployment will shift to a self-hosted Dokku instance on a Proxmox VM, utilizing Dokku's official PostgreSQL plugin for persistent data storage. We will also add required configurations (Procfile, port handling) to ensure Dokku can successfully manage and route traffic to the application.

---

## Problem Frame

The project was originally planned for Render's free tier, which does not offer persistent ephemeral storage, making SQLite unsuitable across deployments. To ensure data durability and provide a "Render-like" git-push deployment experience, we are migrating the data layer to SQLAlchemy, allowing the use of PostgreSQL via Dokku on a self-hosted Proxmox VM.

---

## Requirements Trace

### Core Migration & Data Layer
- R2. Refactor `repository.py` to use SQLAlchemy ORM instead of raw `sqlite3` queries.
- R3. Ensure the database connection automatically supports the `DATABASE_URL` environment variable provided by Dokku.
- R6. Provide a path for existing data migration.
- R7. **(NEW)** Secure user sessions with signed cookies (SessionMiddleware) to prevent identity spoofing in public-facing deployment.

### Infrastructure & Dependencies
- R1. Update Python dependencies to include SQLAlchemy, Alembic, and Psycopg 3 (`psycopg[binary]`).
- R5. Configure the application for Dokku deployment (Procfile, dynamic PORT).
- R8. **(NEW)** Downgrade Python requirement to `^3.12` for compatibility with stable buildpacks.

### Documentation
- R4. Document the Proxmox/Dokku setup and deployment commands.

---

## Scope Boundaries

- Update `pyproject.toml` dependencies.
- Refactor `repository.py` for SQLAlchemy.
- Fallback to local SQLite if no `DATABASE_URL` is provided.
- Create deployment documentation and necessary Dokku configuration files (`Procfile`).
- Create a one-time data migration script to move existing local SQLite data to PostgreSQL.
- **Explicit non-goal**: Changes to core scraping logic or UI.
- **Explicit non-goal**: Provisioning the actual Proxmox VM.

---

## Context & Research

### Relevant Code and Patterns

- `src/sauspiel_scraper/repository.py`: Currently handles raw `sqlite3` connections and executes raw SQL.
- `src/sauspiel_scraper/app/main.py`: The FastAPI application entry point.

---

## Key Technical Decisions

- **ORM Choice**: SQLAlchemy 2.0.
- **Driver Choice**: **Psycopg 3** (`psycopg[binary]`).
- **FastAPI Concurrency**: Transition database-bound web routes from `async def` to standard `def`. This allows FastAPI to run these operations in a dedicated threadpool.
- **Schema Management**:
    - **Development/Test**: Use `Base.metadata.create_all()` for rapid iteration and local SQLite.
    - **Production**: Use **Alembic** as the authoritative source. Configure `alembic/env.py` with `render_as_batch=True` to support SQLite.
- **Dialect Compatibility**:
    - **JSONB Column**: Use SQLAlchemy's `JSON` type with a `JSONB` variant.
    - **GIN Indexing**: Explicitly wrap GIN index definitions with `postgresql_using='gin'`. SQLAlchemy will ignore this when targeting SQLite.
    - **Query Logic**: Implement dialect-aware filtering in the repository. Use `JSONB.contains` for Postgres and `LIKE` for SQLite.
- **Security**:
    - **Signed Sessions**: Replace raw `username` cookies with FastAPI `SessionMiddleware` and a `SESSION_SECRET` (from environment).
    - **SSL**: Enforce `sslmode=require` for PostgreSQL connections in production.
- **Connection Logic**:
    - **URL Sanitization**: Replace `postgres://` with `postgresql://`.
    - **Resilience**: Configure `create_engine` with `pool_pre_ping=True`.
- **Deployment Compatibility**: Dokku requires dynamic port binding via the `$PORT` environment variable and a `Procfile`.

---

## Implementation Units

- U1. **Add Database and Security Dependencies**

**Goal:** Include SQLAlchemy, Alembic, Psycopg 3, and session support in the project.

**Requirements:** R1, R8

**Dependencies:** None

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (via `uv sync`)

**Approach:**
- Add `sqlalchemy`, `alembic`, `psycopg[binary]`, and `itsdangerous` (for session signing).
- Update `pyproject.toml` to `python = "^3.12"`.

**Verification:**
- `uv run python -c "import sqlalchemy, psycopg, alembic"` succeeds.

---

- U2. **Refactor Repository to SQLAlchemy and Alembic**

**Goal:** Abstract data access using SQLAlchemy ORM and configure schema initialization.

**Requirements:** R2, R3

**Dependencies:** U1

**Files:**
- Modify: `src/sauspiel_scraper/repository.py`
- Modify: `src/sauspiel_scraper/app/main.py` (update route signatures)
- Modify: `tests/test_repository.py`
- Create: `alembic.ini` and `alembic/env.py` (via `alembic init`)

**Approach:**
- Define declarative base models for `GameModel` and `UserModel`.
  - `GameModel`: `game_id` (String, PK), `date` (DateTime), `game_type` (String), `data` (JSON).
  - Define GIN index: `Index('idx_games_data_players', GameModel.data['players'], postgresql_using='gin')`.
- Update `Database` initialization:
  - Sanitize `DATABASE_URL`.
  - Configure engine with `pool_pre_ping=True`.
  - Use `create_all()` ONLY if `DATABASE_URL` is a local SQLite path.
- Implement `session_scope()` context manager for background workers.
- Update `src/sauspiel_scraper/app/main.py`:
  - Change database-accessing routes to standard `def`.
  - Implement `get_db` dependency for session injection.
- Update `get_all_games` with dialect check:
  ```python
  if self.engine.dialect.name == "postgresql":
      # use .contains
  else:
      # use .like
  ```

**Verification:**
- The test suite (`pytest tests/`) passes on local SQLite.

---

- U3. **Dokku App Configuration Updates**

**Goal:** Ensure the application runs properly within Dokku's routing and process management.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Create: `Procfile`

**Approach:**
- Create a `Procfile` at the repository root: `web: uvicorn sauspiel_scraper.app.main:app --host 0.0.0.0 --port $PORT`

**Verification:**
- Procfile exists.

---

- U4. **Data Migration Script and Logistics**

**Goal:** Provide an idempotent migration path for existing scraped data.

**Requirements:** R6

**Dependencies:** U2

**Files:**
- Create: `scripts/migrate_sqlite_to_postgres.py`

**Approach:**
- Write a standalone script using `postgresql.insert(...).on_conflict_do_nothing()`.
- **Logistics**: Document the step to `scp` the local `output/sauspiel.db` to the Dokku host before running the script.

**Verification:**
- The script successfully migrates records from a test SQLite database to a test PostgreSQL database.

---

- U5. **Document Dokku Deployment**

**Goal:** Create step-by-step instructions for the VM setup and application deployment.

**Requirements:** R4

**Dependencies:** U3, U4

**Files:**
- Create: `docs/deployment/dokku.md`

**Approach:**
- Provide CLI commands for app creation, plugin installation, and database linking.
- **Add Step**: `dokku run sauspiel-scraper alembic upgrade head` before data migration.
- **Add Step**: Commands to transfer the SQLite database to the Dokku host.

**Verification:**
- Document exists and covers all steps.

---

- U6. **Secure Session Implementation**

**Goal:** Prevent identity spoofing by signing the user session cookie.

**Requirements:** R7

**Dependencies:** U1

**Files:**
- Modify: `src/sauspiel_scraper/app/main.py`
- Modify: `src/sauspiel_scraper/app/auth.py`

**Approach:**
- Add `SessionMiddleware` to the FastAPI app.
- Update auth logic to use `request.session["username"] = ...` instead of a raw cookie.
- Use `SESSION_SECRET` environment variable (with local fallback).

**Verification:**
- Browsing the dashboard without a valid signed session fails.
- Changing the username in browser dev tools does not grant access to other accounts.

---

## System-Wide Impact

- **Event Loop Performance**: By switching web routes to `def`, we ensure the UI remains responsive.
- **Security Posture**: Moving from raw cookies to signed sessions significantly improves the application's readiness for public internet exposure.
- **Dialect Resilience**: The codebase remains functional for local SQLite development while exploiting PostgreSQL-specific performance features in production.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Dialect Incompatibility | Repository uses explicit dialect checks for JSONB containment. |
| Session Hijacking | Sessions are signed with a secret key; documentation includes rotation guidance. |
| Migration Drift | Production uses Alembic; local uses `create_all` only for scaffolding. |
| Event loop starvation | All DB-bound routes moved to threadpool (`def`). |

---

## Operational Notes

- **Backups**: Dokku's PostgreSQL plugin supports `dokku postgres:export`. It is recommended to set up a cron job to backup the database to the Proxmox host or external storage.
- **Secret Rotation**: Rotate `FERNET_KEY` and `SESSION_SECRET` if the environment is compromised.
