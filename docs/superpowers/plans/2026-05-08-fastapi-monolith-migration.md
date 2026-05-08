# FastAPI Multi-User Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition the Sauspiel Scraper from Streamlit to a hosted FastAPI monolith with multi-user support and background scraping.

**Architecture:** A single-process FastAPI application with an integrated APScheduler for background scraping. SQLite is used for storage with symmetric encryption for user passwords.

**Tech Stack:** FastAPI, Jinja2, HTMX, APScheduler, cryptography, SQLite, Pydantic, Pandas/Plotly.

---

## File Structure

- `src/sauspiel_scraper/app/`:
    - `main.py`: Core FastAPI app and background worker entry point.
    - `auth.py`: (New) Encryption and session management logic.
    - `templates/`: (New) Jinja2 HTML templates.
    - `static/`: (New) CSS and HTMX.
- `src/sauspiel_scraper/repository.py`: Modified to support `users` table and multi-user filtering.
- `pyproject.toml`: Updated dependencies.

---

## Tasks

### Task 1: Environment & Dependency Setup

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`

- [ ] **Step 1: Update dependencies**
Add `fastapi`, `uvicorn`, `jinja2`, `apscheduler`, `cryptography`, `python-multipart` (for forms), and `itsdangerous` (for sessions). Remove `streamlit`.
- [ ] **Step 2: Sync environment**
Run: `uv sync`
- [ ] **Step 3: Create .env.example**
Define `FERNET_KEY` and `DATABASE_URL`.
- [ ] **Step 4: Commit**
`git commit -m "chore: setup fastapi and security dependencies"`

### Task 2: Database Schema & Repository Update

**Files:**
- Modify: `src/sauspiel_scraper/repository.py`
- Test: `tests/test_repository_multiuser.py` (New)

- [ ] **Step 1: Write test for multi-user schema**
Verify we can save/fetch users and filter games by player name.
- [ ] **Step 2: Add `users` table and update `Database` class**
Add `CREATE TABLE IF NOT EXISTS users` (username, encrypted_password, last_scraped_at).
- [ ] **Step 3: Update `get_all_games` to support filtering**
Add an optional `username` filter to the query.
- [ ] **Step 4: Verify tests pass**
Run: `pytest tests/test_repository_multiuser.py`
- [ ] **Step 5: Commit**
`git commit -m "feat: update database schema for multi-user support"`

### Task 3: Encryption & Auth Utilities

**Files:**
- Create: `src/sauspiel_scraper/app/auth.py`
- Test: `tests/test_auth.py` (New)

- [ ] **Step 1: Implement Fernet encryption helper**
Methods to encrypt/decrypt strings using an env var key.
- [ ] **Step 2: Write tests for encryption**
Ensure `decrypt(encrypt(val)) == val`.
- [ ] **Step 3: Verify tests pass**
Run: `pytest tests/test_auth.py`
- [ ] **Step 4: Commit**
`git commit -m "feat: add encryption utilities for user credentials"`

### Task 4: Core FastAPI & Dashboard (Phase 1)

**Files:**
- Modify: `src/sauspiel_scraper/app/main.py`
- Create: `src/sauspiel_scraper/app/templates/base.html`
- Create: `src/sauspiel_scraper/app/templates/dashboard.html`

- [ ] **Step 1: Scaffold FastAPI app**
Set up Jinja2 templates and a basic `@app.get("/")` dashboard route.
- [ ] **Step 2: Create base templates**
Use a simple CSS framework (like Pico.css) and include HTMX.
- [ ] **Step 3: Implement Dashboard view**
Fetch games for the logged-in user and render a simple table.
- [ ] **Step 4: Verify UI renders**
Run `uvicorn sauspiel_scraper.app.main:app --reload` and check browser.
- [ ] **Step 5: Commit**
`git commit -m "feat: initial fastapi dashboard with jinja2"`

### Task 5: Background Worker (APScheduler)

**Files:**
- Modify: `src/sauspiel_scraper/app/main.py`

- [ ] **Step 1: Integrate APScheduler**
Initialize `BackgroundScheduler` on FastAPI startup.
- [ ] **Step 2: Implement Scrape Task**
Loop through all users in DB, decrypt passwords, and call `SauspielScraper.scrape_all_previews()`.
- [ ] **Step 3: Add manual trigger endpoint**
Create `@app.post("/scrape")` for HTMX to trigger an immediate scrape.
- [ ] **Step 4: Verify background task runs**
Log success/failure in the background loop.
- [ ] **Step 5: Commit**
`git commit -m "feat: integrated background worker for automated scraping"`

### Task 6: Analytics Port & UI Polish

**Files:**
- Modify: `src/sauspiel_scraper/app/main.py`
- Modify: `src/sauspiel_scraper/app/templates/dashboard.html`

- [ ] **Step 1: Port Plotly charts**
Call existing `render_analytics` logic, but extract the Plotly HTML/JSON for Jinja2.
- [ ] **Step 2: Add HTMX interactivity**
Add a "Scrape Status" indicator that updates via HTMX polling.
- [ ] **Step 3: Final Verification**
Test full flow: Login -> Background Scrape -> Dashboard Update.
- [ ] **Step 4: Commit**
`git commit -m "feat: port analytics and add htmx polling"`
