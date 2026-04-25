---
module: sauspiel_scraper
date: 2026-04-25
problem_type: architecture_pattern
component: database
severity: high
applies_when:
  - "Scraping core is tightly coupled with database persistence and UI logic"
  - "Missing or malformed scraped data causes fatal crashes in the main loop"
  - "Strict type validation is required to prevent data corruption"
symptoms:
  - "Fatal break on missing games during scraping"
  - "Silent error swallowing in database operations"
  - "Literal 'None' strings appearing in persisted data"
root_cause: missing_validation
resolution_type: code_fix
tags:
  - pydantic
  - architectural-decoupling
  - repository-pattern
  - web-scraping
---

# Architectural Decoupling using Pydantic Models and Repositories

## Context
The Sauspiel scraper, database storage, and Streamlit UI were originally tightly coupled. The system relied on raw, nested dictionaries and manual string parsing at every layer. This led to high maintenance costs, brittle tests, and "silent failure" modes where corrupt data would pass through the scraper only to crash the UI later.

### What was tried before (session history)
*   **Monolithic Core**: A single class handled HTML parsing, network requests, and SQLite management.
*   **Dictionary-based Data**: Unvalidated raw dictionaries were passed between layers.
*   **Direct Database Dependency**: The UI directly instantiated database helpers, preventing portability.

## Guidance
1.  **Establish a Domain Contract:** Define strict Pydantic models (e.g., `Game`, `GameMeta`) in a dedicated `models.py`. This acts as the "source of truth" for data structure.
2.  **Isolate the Storage Layer:** Extract database logic into a `GameRepository`. Ensure it accepts and returns domain models, handling serialization internally.
3.  **Validation Strategy:** 
    *   **Strict Ingress:** The scraper must return validated domain models immediately after parsing. If the data is invalid, fail loudly.
    *   **Resilient Egress:** When loading historical records from a database, use specific exception handling (e.g., `pydantic.ValidationError`) and logging to skip corrupt legacy rows without crashing the application.
4.  **Decouple UI from Persistence:** The UI should interact only with the Repository and Domain Models.

## Why This Matters
*   **Maintainability:** Changes to the HTML structure only require updates to the models and scraper, rather than every UI component.
*   **Strict Validation:** Pydantic automatically validates types and mandatory fields, catching errors at the source.
*   **Resilience:** Explicit error handling in retrieval ensures the UI remains functional even if some historical data is malformed.

## When to Apply
Apply this pattern when changing your data storage or representation requires modifying core logic, or when moving from unvalidated dictionaries to structured, typed data.

## Examples
### Before (Dictionary-based & Coupled)
```python
# In core.py
def scrape_game(self, gid):
    return {"id": gid, "meta": {"date": "..."}}

# In app.py
data = scraper.scrape_game(gid)
game_date = data.get("meta", {}).get("date") # Brittle access
```

### After (Pydantic-based & Decoupled)
```python
# In models.py
from pydantic import BaseModel

class Game(BaseModel):
    game_id: str
    meta: GameMeta

# In repository.py
import logging
from pydantic import ValidationError

def get_all_games(self) -> list[Game]:
    rows = self.conn.execute("SELECT data FROM games")
    games = []
    for r in rows:
        try:
            games.append(Game.model_validate_json(r[0]))
        except ValidationError as e:
            logging.warning(f"Skipping corrupt record: {e}")
            continue
    return games

# In app.py
games = repository.get_all_games()
if games:
    game_date = games[0].meta.date # Strict dot notation
```

## Related
*   [Architecture Decoupling Requirements](docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md)
*   [Refactor Architecture Decoupling Plan](docs/plans/2026-04-25-001-refactor-architecture-decoupling-plan.md)
