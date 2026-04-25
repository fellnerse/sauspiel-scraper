---
date: 2026-04-25
topic: architecture-decoupling
---

# Architecture Decoupling (Scraper & App)

## Problem Frame

The current crawler, data layer, and representation layer (Streamlit) are too intertwined. The Streamlit app relies on the `SauspielScraper` core instance and raw Pandas dataframe processing of the database. The goal is to decouple these layers so the web UI (representation layer) can be hosted separately (eventually as a browser-only deployment, e.g., Pyodide), without depending on the exact execution or database format of the scraper.

---

## Requirements

**Domain Modeling**
- R1. The system must define a shared `models.py` using `pydantic` to represent the core domain model (e.g., `Game`, `Trick`, etc.).
- R2. The scraper must return these shared Pydantic `Game` objects instead of raw dictionaries.

**CLI & Scraper Layer**
- R3. The CLI must execute the scraper, receive Pydantic `Game` objects, and serialize them to JSON (or save to a file) without directly coupling to the SQLite database.

**Representation & App Layer**
- R4. The Streamlit app must consume Pydantic `Game` objects (either via an internal `SqliteRepository` or direct JSONL import).
- R5. The Pandas analytics transformation (`process_game_data`) must operate on the shared Pydantic models (or its DB representation) as pure UI rendering logic, not as part of the core scraper.
- R6. The application architecture must support a future where the code runs entirely in the browser (e.g., SQLite DB in the browser, no separate backend server required).

**Testing**
- R7. Implement at least one test that uses a static HTML fixture (a real game page) to verify the scraper correctly extracts and constructs the expected Pydantic domain model.

---

## Success Criteria

- The Streamlit app and CLI can operate independently on the shared Pydantic domain models.
- The `core.py` (or equivalent domain module) no longer contains UI-specific data processing.
- The scraper's logic is fully decoupled from the storage mechanism (SQLite vs. JSON).

---

## Scope Boundaries

- Migrating the Streamlit app to actual WASM/browser-only deployment is deferred for later; the goal now is purely architectural readiness.
- Modifying the scraping logic itself (how it parses HTML) beyond returning Pydantic models is excluded.

---

## Key Decisions

- **Pydantic for Domain Models**: Selected over standard dataclasses to leverage automatic validation (crucial for messy HTML scraping) and trivial JSON serialization, at the cost of an extra dependency (which is Pyodide-compatible).

---

## Next Steps

-> /ce-plan
