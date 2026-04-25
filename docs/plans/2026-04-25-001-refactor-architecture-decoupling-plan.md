---
title: Refactor Architecture Decoupling
type: refactor
status: completed
date: 2026-04-25
origin: docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md
---

# Refactor Architecture Decoupling

## Overview

Decouple the web UI (Streamlit) from the scraping core by introducing a Pydantic-based domain model as the shared contract. Move storage logic out of the core scraper module, ensuring the core only focuses on fetching and returning typed `Game` models. Update the CLI to output JSON directly and the app layer to consume these models, paving the way for future browser-only (WASM/Pyodide) deployments.

---

## Problem Frame

The current crawler, data layer, and representation layer (Streamlit) are too intertwined. The Streamlit app relies on the `SauspielScraper` core instance and raw Pandas dataframe processing of the database. The goal is to decouple these layers so the web UI (representation layer) can be hosted separately, without depending on the exact execution or database format of the scraper.

---

## Requirements Trace

- R1. Define a shared `models.py` using `pydantic` to represent the core domain model (`Game`, `Trick`, etc.).
- R2. Scraper must return these shared Pydantic `Game` objects instead of raw dictionaries.
- R3. CLI must execute the scraper, receive Pydantic `Game` objects, and serialize them to JSON (or save to a file) without directly coupling to the SQLite database.
- R4. Streamlit app must consume Pydantic `Game` objects (via internal `SqliteRepository` or JSONL import).
- R5. Pandas analytics transformation (`process_game_data`) must operate on the shared Pydantic models as pure UI rendering logic.
- R6. Architecture must support future browser-only execution.
- R7. Implement at least one test that uses a static HTML fixture (a real game page) to verify the scraper correctly extracts and constructs the expected Pydantic domain model.

---

## Scope Boundaries

- Migrating the Streamlit app to actual WASM/browser-only deployment is deferred for later; the goal now is purely architectural readiness.
- Modifying the scraping logic itself (how it parses HTML) beyond returning Pydantic models is excluded.

---

## Context & Research

### Relevant Code and Patterns

- `src/sauspiel_scraper/core.py` currently holds both `SauspielScraper` and `Database`.
- `src/sauspiel_scraper/app.py` directly depends on `core.py` for `Database` and contains `process_game_data`.
- `src/sauspiel_scraper/main.py` is the Typer CLI which currently depends on `Database`.
- `tests/test_parser.py` uses `tests/fixtures/detail.html` but currently asserts against plain dictionaries.

---

## Key Technical Decisions

- **Pydantic for Domain Models**: Selected over standard dataclasses to leverage automatic validation and trivial JSON serialization. Pyodide compatibility supports the future browser-only goal.
- **Extract Storage Layer**: `Database` will be moved from `core.py` to `repository.py` (or similar) owned by the application layer, ensuring the core scraper knows nothing about SQLite.

---

## Open Questions

### Deferred to Implementation

- The exact field types and optionality in the Pydantic models will be determined by observing the existing messy HTML parsed structure in `test_parser.py`.

---

## Implementation Units

- U1. **Domain Models**
  **Goal:** Define the Pydantic classes for the shared contract.
  **Requirements:** R1
  **Dependencies:** None
  **Files:**
  - Create: `src/sauspiel_scraper/models.py`
  **Approach:**
  - Create `Game`, `Trick`, and any nested structures (like meta data or initial hands) as `pydantic.BaseModel`.
  - Use `Field` for defaults and potential alias mapping if needed.
  **Test scenarios:**
  - Test expectation: none -- this is pure data structure definition.
  **Verification:**
  - The models load correctly and validate basic data.

- U2. **Refactor Scraper to Return Models**
  **Goal:** Update `SauspielScraper` to return instances of the new Pydantic models.
  **Requirements:** R2
  **Dependencies:** U1
  **Files:**
  - Modify: `src/sauspiel_scraper/core.py`
  **Approach:**
  - Update `scrape_game` to explicitly parse the raw HTML extractions into the strict Pydantic schema before instantiating the `Game` model. This may require a mapping step for messy fields like `meta`.
  - Update `get_game_list_paginated` to yield a list of basic meta dictionaries or a lightweight `GamePreview` model.
  **Test scenarios:**
  - Test expectation: none -- covered in U6's fixture tests.
  **Verification:**
  - The scraper signature reflects the Pydantic models.

- U3. **Decouple Database Storage**
  **Goal:** Move `Database` out of the core scraper file to separate concerns.
  **Requirements:** R4, R6
  **Dependencies:** U1, U2
  **Files:**
  - Modify: `src/sauspiel_scraper/core.py`
  - Create: `src/sauspiel_scraper/repository.py`
  **Approach:**
  - Extract the SQLite `Database` class into `repository.py`.
  - Update it to accept and return `Game` Pydantic models, serializing them using `.model_dump_json()` and deserializing using `Game.model_validate_json()`.
  **Test scenarios:**
  - Happy path: Save a `Game` model and retrieve it successfully via SQLite.
  **Verification:**
  - `core.py` no longer contains SQLite dependencies.

- U4. **Update CLI for JSON Serialization**
  **Goal:** Update Typer CLI to handle the decoupled scraper and database.
  **Requirements:** R3
  **Dependencies:** U2, U3
  **Files:**
  - Modify: `src/sauspiel_scraper/main.py`
  **Approach:**
  - Change the `export` command to directly use the new `Database` from `repository.py` and output `Game` models to JSONL.
  - Change the `scrape` command to pass models to the `Database`.
  **Test scenarios:**
  - Test expectation: none -- CLI plumbing change.
  **Verification:**
  - `sauspiel-scraper export` generates valid JSONL files containing Pydantic-serialized data.

- U5. **Update Streamlit App Representation**
  **Goal:** Update Streamlit to consume Pydantic models and use the separated database repository.
  **Requirements:** R4, R5
  **Dependencies:** U3
  **Files:**
  - Modify: `src/sauspiel_scraper/app.py`
  **Approach:**
  - Import `Database` from `repository.py`.
  - Refactor `process_game_data` to accept `list[Game]` and extract the necessary fields using Pydantic's dot notation (e.g., `game.meta.wert`) instead of dictionary `.get()`.
  - Ensure any Streamlit scraping loops are updated to use dot notation for the returned models.
  **Test scenarios:**
  - Test expectation: none -- Streamlit UI rendering logic updates.
  **Verification:**
  - The Streamlit app runs without errors and renders the analytics dashboard correctly using the new domain models.

- U6. **Static HTML Fixture Tests**
  **Goal:** Add test coverage to verify that the scraper correctly builds Pydantic models from real HTML.
  **Requirements:** R7
  **Dependencies:** U2
  **Files:**
  - Modify: `tests/test_parser.py`
  **Approach:**
  - Update existing tests (`test_parse_detail_page`) that use `detail.html` to assert the returned object is a `Game` model.
  - Validate specific fields (e.g., `game_id`, `players`, `tricks`) against the model properties.
  **Test scenarios:**
  - Covers R7. Happy path: Parse `detail.html` and verify the resulting `Game` model has the exact expected attributes (e.g., 4 players, 6 tricks).
  **Verification:**
  - `pytest tests/test_parser.py` passes successfully.

---

## System-Wide Impact

- **Interaction graph:** `core.py` no longer manages the SQLite DB. `main.py` and `app.py` act as the orchestrators connecting `core.py` to `repository.py`.
- **Data format:** Existing SQLite databases may break if the structure of `Game.model_dump_json()` differs significantly from the current raw dictionary JSON dumps. A schema drop or clearing might be necessary.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Existing SQLite data incompatibility | Advise the user to clear the existing database or implement a graceful fallback to ignore invalid historical rows. |
| Pydantic strictness breaking on messy HTML | Enforce strict typing in the `Game` model by identifying guaranteed fields (e.g. `game_id`, `players`, `date`, `tricks`) and keeping them required. For truly messy dictionary data (like the current `meta`), implement an explicit mapper/parser step in the scraper before instantiating the model, rather than falling back to `Any` or `Optional` everywhere. If parsing fails, the data is genuinely corrupt and should fail loudly. |

---

## Sources & References

- **Origin document:** docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md
