# Design Spec: FastAPI Multi-User Scraper Monolith

## 1. Introduction
This project transitions the existing Sauspiel Scraper from a Streamlit experimental UI to a robust, hosted "FastAPI Monolith." The goal is to provide a multi-user platform where background scraping happens autonomously, allowing users to view their cards and profit analytics across different devices.

## 2. Architecture
The system follows a "Glorified Monolith" architecture (Option 3) for rapid deployment and 80/20 value.

- **Web Server:** FastAPI serving both a REST API and Jinja2-rendered HTML.
- **UI:** Server-Side Rendering (SSR) with Jinja2, enhanced with HTMX for SPA-like interactivity.
- **Background Worker:** `APScheduler` running in a side-thread within the FastAPI process.
- **Persistence:** SQLite database with two primary tables: `users` and `games`.
- **Encryption:** `cryptography.fernet` for securing user passwords.

## 3. Component Details

### 3.1 Web Layer (FastAPI)
- **Authentication:** Users provide Sauspiel credentials via a web form.
- **Dashboard:** Fetches data from SQLite, processes it via existing `analytics.py` (Pandas/Plotly), and renders it via Jinja2.
- **HTMX Integration:** Handles "Scrape Now" triggers and dynamic updates of game lists without page reloads.

### 3.2 Background Worker (APScheduler)
- **Schedule:** Every 6 hours (configurable).
- **Process:**
    1. Retrieve all users from `users` table.
    2. Decrypt password using `ENCRYPTION_KEY` env var.
    3. Instantiate `SauspielScraper`.
    4. Fetch and save new games to the shared `games` table.
    5. Update `last_scraped_at` timestamp for the user.

### 3.3 Data Layer (SQLite)
- **`users` table:**
    - `username` (PK)
    - `encrypted_password`
    - `created_at`
    - `last_scraped_at`
- **`games` table (Existing, with updates):**
    - `game_id` (PK)
    - `date`
    - `game_type`
    - `data` (JSON blob)
- **Privacy/Isolation:** Games are stored in a single table. Views are filtered dynamically by the logged-in user's name appearing in the game's `players` list within the JSON blob.

### 3.4 Security
- **Passwords:** Never stored in plain text. Encrypted using a symmetric key (`FERNET_KEY`) stored in Render's environment variables.
- **Session Management:** FastAPI-Users or simple Secure Cookie sessions to keep users logged into the dashboard.

## 4. Implementation Phases

1. **Scaffold & Migration:** Add dependencies (FastAPI, uvicorn, jinja2, apscheduler, cryptography) and initialize the new `Database` schema.
2. **Auth & Encryption:** Implement the encryption utility and the Login/Registration flow.
3. **Background Worker:** Integrate APScheduler and wire it to the existing `SauspielScraper`.
4. **Dashboard & Analytics:** Ports existing Streamlit analytics logic to FastAPI/Jinja2.
5. **Deployment:** Configure Render `render.yaml` with a Persistent Disk for the SQLite file.

## 5. Success Criteria
- [ ] Users can log in with Sauspiel credentials.
- [ ] Scraping runs in the background even when no one is on the site.
- [ ] Dashboard shows analytics for the logged-in user only.
- [ ] Data persists across server restarts on Render.
