---
title: Dokku Deployment & PostgreSQL Migration
type: feat
status: active
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

- R1. Update Python dependencies to include SQLAlchemy, Alembic, and a PostgreSQL driver.
- R2. Refactor `repository.py` to use SQLAlchemy ORM instead of raw `sqlite3` queries.
- R3. Ensure the database connection automatically supports the `DATABASE_URL` environment variable provided by Dokku.
- R4. Document the Proxmox/Dokku setup and deployment commands.
- R5. Configure the application for Dokku deployment (Procfile, dynamic PORT).
- R6. Provide a path for existing data migration.

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

- `src/sauspiel_scraper/repository.py`: Currently handles raw `sqlite3` connections and executes raw SQL for `games` and `users` tables. The `Database` class acts as the central interface.
- `src/sauspiel_scraper/app/main.py`: The FastAPI application entry point, which currently relies on a hardcoded port.

---

## Key Technical Decisions

- **ORM Choice**: SQLAlchemy. It provides a robust abstraction layer, making it trivial to switch between SQLite for local development and PostgreSQL for production.
- **Schema Management**: Alembic will be introduced to manage schema evolution safely in production, ensuring changes to the models can be consistently applied.
- **Driver**: `psycopg2-binary` for standard synchronous PostgreSQL connections.
- **JSON Column & Querying**: Use SQLAlchemy's `JSON` type configured with a `JSONB` variant for PostgreSQL to ensure semantic query correctness and allow for GIN indexing. The SQLite fallback will still utilize text-based representations. Querying for games by player will conditionally use JSON containment (`contains`) on PostgreSQL and string matching (`LIKE`) on SQLite.
- **Connection Logic**: `repository.py` will read `os.environ.get("DATABASE_URL")`. If it exists, it connects via PostgreSQL. Dokku provides `postgres://` URLs, which will be auto-replaced with `postgresql://` to satisfy modern SQLAlchemy requirements.
- **Session Management**: Transition away from `threading.Lock` to using proper SQLAlchemy session management (e.g., `sessionmaker`) to ensure thread-safe operations, especially important given the background tasks scheduling.
- **Deployment Compatibility**: Dokku requires dynamic port binding via the `$PORT` environment variable and a `Procfile` to identify the correct web process. These will be explicitly configured.

---

## Implementation Units

- U1. **Add Database Dependencies**

**Goal:** Include SQLAlchemy, Alembic, and PostgreSQL driver in the project.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (via `uv sync`)

**Approach:**
- Add `sqlalchemy`, `alembic`, and `psycopg2-binary` to the `dependencies` array.
- The implementer will need to run `uv sync` to generate the updated lockfile.

**Verification:**
- `uv run python -c "import sqlalchemy, psycopg2, alembic"` succeeds.

---

- U2. **Refactor Repository to SQLAlchemy and Alembic**

**Goal:** Abstract data access using SQLAlchemy ORM and configure schema initialization.

**Requirements:** R2, R3

**Dependencies:** U1

**Files:**
- Modify: `src/sauspiel_scraper/repository.py`
- Modify: `tests/test_repository.py` (if any SQL-specific mocks/tests exist)
- Create: `alembic.ini` and `alembic/env.py` (via `alembic init`)

**Approach:**
- Define declarative base models for `GameModel` and `UserModel`.
  - `GameModel`: `game_id` (String, PK), `date` (String), `game_type` (String), `data` (JSON, with JSONB variant and GIN index for postgres).
  - `UserModel`: `username` (String, PK), `encrypted_password` (String), `last_scraped_at` (String).
- Update `Database` initialization: auto-replace `postgres://` with `postgresql://` in `DATABASE_URL`. Configure `create_engine` with connection pool settings (`pool_pre_ping=True`, `pool_recycle=300`) to handle managed PostgreSQL environments safely.
- Incorporate `Base.metadata.create_all(self.engine)` upon connection to ensure tables exist, and configure Alembic to track future schema changes.
- Remove `threading.Lock` and instantiate a standard `sessionmaker` bound to the engine. Refactor all methods to use short-lived sessions (e.g., context managers `with self.Session() as session:`) to prevent connection leaks across background tasks and requests.
- Update `get_all_games`: use dialect-specific filtering (PostgreSQL uses `data['players'].contains([username])`; SQLite uses `.like()`).

**Patterns to follow:**
- Keep the exact existing public method signatures of the `Database` class so `main.py` and `app/main.py` do not break.

**Test scenarios:**
- Happy path: Initializing `Database` without `DATABASE_URL` creates a local sqlite file with initialized schema.
- Happy path: Saving and retrieving a game uses ORM and accurately persists JSON blobs.
- Integration: Retrieving games filtered by username returns correct results using the dialect-appropriate filter logic.

**Verification:**
- The test suite (`pytest tests/`) passes.

---

- U3. **Dokku App Configuration Updates**

**Goal:** Ensure the application runs properly within Dokku's routing and process management.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Create: `Procfile`
- Modify: `src/sauspiel_scraper/app/main.py`

**Approach:**
- Create a `Procfile` at the repository root defining the web process: `web: uvicorn sauspiel_scraper.app.main:app --host 0.0.0.0 --port $PORT`
- Modify the FastAPI entry point in `src/sauspiel_scraper/app/main.py` (if it contains hardcoded uvicorn run commands) to use `os.environ.get("PORT", 8000)` instead of a hardcoded port.

**Verification:**
- Procfile exists. Running `uvicorn` with `$PORT` set to a custom value successfully binds to that port.

---

- U4. **Data Migration Script**

**Goal:** Provide a migration path for existing scraped data in local SQLite.

**Requirements:** R6

**Dependencies:** U2

**Files:**
- Create: `scripts/migrate_sqlite_to_postgres.py`

**Approach:**
- Write a one-off standalone script that:
  - Connects to the legacy `output/sauspiel.db` SQLite database using standard `sqlite3` or SQLAlchemy.
  - Connects to the new PostgreSQL database defined by `DATABASE_URL`.
  - Iterates over the `users` and `games` tables and bulk inserts the records into the new database, gracefully handling existing keys.

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
- Write a Markdown guide detailing how to install Dokku on the VM.
- Provide the CLI commands to:
  - Create the dokku app (`dokku apps:create sauspiel-scraper`).
  - Install the postgres plugin (`sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git`).
  - Create and link the database (`dokku postgres:create sauspiel-db`, `dokku postgres:link sauspiel-db sauspiel-scraper`).
  - Add required environment variables (`dokku config:set sauspiel-scraper FERNET_KEY=...`).
  - Deploy the code using git push.
  - Run the data migration script inside the dokku container: `dokku run sauspiel-scraper python scripts/migrate_sqlite_to_postgres.py`.

**Verification:**
- Document exists and accurately covers all required steps.

---

## System-Wide Impact

- **Database Engine**: Transitioning from SQLite to PostgreSQL removes file persistence constraints. Local behavior remains identical using SQLAlchemy.
- **Connection Lifecycle & Concurrency**: We replace the manual `threading.Lock` with robust SQLAlchemy session management. Proper connection pooling configuration (`pool_recycle`, `pool_pre_ping`) mitigates the risk of idle connections dropping in PostgreSQL.
- **Environment Variables**: The system will actively rely on and sanitize `DATABASE_URL` when deployed, and rely on `PORT` for web server binding.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Dokku injecting `postgres://` instead of `postgresql://` | Handle URL schema replacement programmatically in the `Database` constructor before feeding it to SQLAlchemy. |
| Performance degradation over time with large dataset | JSONB column and GIN indexing ensures rapid array containment queries for PostgreSQL. |
