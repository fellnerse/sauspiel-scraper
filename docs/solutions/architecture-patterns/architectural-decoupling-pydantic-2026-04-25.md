---
module: sauspiel_scraper
date: 2026-04-25
last_updated: 2026-04-25
problem_type: architecture_pattern
component: database
severity: high
applies_when:
  - "Scraping core is tightly coupled with database persistence and UI logic"
  - "Missing or malformed scraped data causes fatal crashes in the main loop"
  - "Strict type validation is required to prevent data corruption"
  - "Streamlit app logic is monolithic, mixing UI and data processing"
symptoms:
  - "Fatal break on missing games during scraping"
  - "Silent error swallowing in database operations"
  - "Literal 'None' strings appearing in persisted data"
  - "UI code is difficult to test because it's coupled with Streamlit components"
root_cause: missing_validation
resolution_type: code_fix
tags:
  - pydantic
  - architectural-decoupling
  - repository-pattern
  - web-scraping
  - streamlit
  - modular-design
---

# Architectural Decoupling: Domain Models, Repositories, and Modular UI

## Context
The Sauspiel scraper system (crawler, storage, and UI) was originally tightly coupled. It relied on raw, nested dictionaries and mixed business logic with UI rendering. This led to high maintenance costs, brittle tests, and fatal crashes when encountering malformed data or missing fields.

### What was tried before
*   **Monolithic Core**: A single class handled HTML parsing, network requests, and SQLite management.
*   **Mixed UI & Logic**: `app.py` contained both Streamlit layout code and heavy Pandas data transformations.
*   **Dictionary-based Data**: Unvalidated raw dictionaries were passed between layers, making dot-notation access impossible.

## Guidance
1.  **Establish a Domain Contract:** Define strict Pydantic models (e.g., `Game`, `GameMeta`) in a dedicated `models.py`.
2.  **Isolate the Storage Layer:** Extract database logic into a `Database` repository (e.g., in `repository.py`). Handle serialization internally using `.model_dump_json()` and `.model_validate_json()`.
3.  **Modularize UI Logic:** Split monolithic Streamlit apps into a dedicated package (`sauspiel_scraper.app`) with clear responsibilities:
    *   `processing.py`: Pure logic for data transformation (e.g., Pandas operations) that can be tested independently of Streamlit.
    *   `presentation.py`: Reusable UI components and rendering logic.
    *   `session.py`: Session persistence and authentication state.
    *   `main.py`: Lean orchestration of the above modules.
4.  **Decouple from Frameworks:** Keep data processing functions "pure" (input: domain models, output: dataframes/metrics) so they remain testable via standard `pytest`.

## Why This Matters
*   **Testability:** Data processing can be verified with static unit tests without spinning up a Streamlit server.
*   **Maintainability:** Changes to the UI (presentation) don't risk breaking the data processing logic.
*   **Strict Validation:** Pydantic catches structural errors at the ingress point (scraper) rather than failing late in the UI.
*   **Portability:** The modular structure allows for future deployment targets (e.g., WASM/Pyodide) by swapping out the repository or orchestration layer.

## When to Apply
Apply this pattern when your application mixes data fetching, persistence, and representation, or when unit testing your business logic becomes difficult due to framework dependencies.

## Examples

### Modular UI Package Structure
```text
src/sauspiel_scraper/app/
├── __init__.py      # Package entry points (e.g., run_app)
├── main.py          # Streamlit orchestration
├── presentation.py  # UI rendering (render_analytics)
├── processing.py    # Pure data transformation (process_game_data)
└── session.py       # Session management
```

### Pure Processing Logic (Testable)
```python
# In sauspiel_scraper/app/processing.py
def process_game_data(games: list[Game], me: str) -> pd.DataFrame:
    # Pure Pandas/logic, no streamlit imports here
    rows = [{"game_id": g.game_id, "won": "gewonnen" in g.meta.spielausgang} for g in games]
    return pd.DataFrame(rows)
```

### Decoupled Presentation
```python
# In sauspiel_scraper/app/presentation.py
import streamlit as st
def render_analytics(df: pd.DataFrame):
    st.header("Analytics")
    st.plotly_chart(...)
```

## Related
*   [Architecture Decoupling Requirements](docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md)
*   [Refactor Architecture Decoupling Plan](docs/plans/2026-04-25-001-refactor-architecture-decoupling-plan.md)
