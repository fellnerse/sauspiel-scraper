## Summary
This PR decouples the scraping core from the database and presentation layers by introducing strict Pydantic domain models (`Game`, `Trick`, etc.). The scraper now explicitly parses HTML into these models, and SQLite logic has been isolated into a new `repository.py` module. The CLI and Streamlit app have been updated to interact with the repository and pure domain models, paving the way for future browser-only deployment (e.g. Pyodide). 

## Changes
- **Domain Models:** Created `Game`, `GameMeta`, `Trick`, and `GamePreview` using `pydantic.BaseModel`.
- **Scraper:** Updated `scrape_game` and `get_game_list_paginated` to explicitly map HTML fields to Pydantic models.
- **Repository:** Extracted SQLite `Database` implementation out of `core.py` into `repository.py`. Gracefully ignores invalid/legacy data rows.
- **CLI & Web App:** Updated Typer `main.py` and Streamlit `app.py` to use Pydantic dot notation.
- **Testing:** Extended parser fixture tests to assert strongly typed Pydantic instances. Added missing tests for CLI, repository error handling, and core module edge cases.

## Post-Deploy Monitoring & Validation
No additional operational monitoring required — this is an architectural decoupling refactor.

<hr>
<footer>
  <sub>🤖 Compound Engineered</sub>
</footer>
