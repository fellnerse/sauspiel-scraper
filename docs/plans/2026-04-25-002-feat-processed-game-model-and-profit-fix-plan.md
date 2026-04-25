---
title: "feat: ProcessedGame model and profit calculation fix"
type: feat
status: active
date: 2026-04-25
origin: docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md
---

# feat: ProcessedGame model and profit calculation fix

## Overview

Introduce a `ProcessedGame` Pydantic model to formalize the output of game data processing. This enables better unit testing of the analytics logic. Additionally, fix a bug where profit for opponents was calculated incorrectly (it was mirroring the declarer's profit instead of being the inverse).

---

## Problem Frame

Currently, `process_game_data` returns a `pd.DataFrame` containing raw dictionaries. This makes it difficult to write granular unit tests for the business logic (like profit calculation) without dealing with Pandas index/column boilerplate. Furthermore, the current profit calculation is declarer-centric and incorrect for opponents: if a declarer loses 30 cents, the opponent should win 30 cents, but currently, both are shown as losing 30 cents.

---

## Requirements Trace

- R1. Define `ProcessedGame` Pydantic model in `src/sauspiel_scraper/models.py`.
- R2. Update `process_game_data` to return `list[ProcessedGame]`.
- R3. Fix profit calculation: Opponents win when the declarer loses, and vice versa.
- R4. Provide a `games_to_df` helper for compatibility with existing Streamlit charts.
- R5. Update `render_analytics` to use the new return type.
- R6. Add comprehensive tests for different roles and outcomes.

---

## Scope Boundaries

- **In Scope**: `src/sauspiel_scraper/models.py`, `src/sauspiel_scraper/app/analytics.py`, `tests/test_ui_processing.py`.
- **Out of Scope**: Changing the visual appearance of the charts or tables in Streamlit.

---

## Context & Research

### Relevant Code and Patterns

- `src/sauspiel_scraper/models.py`: Contains `Game` and `GameMeta` models.
- `src/sauspiel_scraper/app/analytics.py`: Contains `process_game_data` and `render_analytics`.
- `tests/test_ui_processing.py`: Existing tests for `process_game_data`.

### Institutional Learnings

- `docs/solutions/architecture-patterns/architectural-decoupling-pydantic-2026-04-25.md`: Advises on using Pydantic for shared contracts and keeping processing logic "pure".

---

## Key Technical Decisions

- **Personal Profit Logic**: The `net_profit_cents` field in `ProcessedGame` will represent the profit/loss from the perspective of the user `me`.
- **DataFrame Compatibility**: We'll use `pd.DataFrame([g.model_dump() for g in processed_games])` in a helper function to ensure the UI layer remains unchanged.

---

## Open Questions

### Resolved During Planning

- **Question**: How to handle cumulative profit in the new model?
- **Resolution**: Cumulative profit is a sequence-dependent property and fits better in the DataFrame/UI layer (or a wrapper) rather than the individual `ProcessedGame` model. We will keep it in the DataFrame conversion step.

---

## Implementation Units

- U1. **Define ProcessedGame Model**
  **Goal:** Add the new model to `models.py`.
  **Requirements:** R1
  **Files:**
  - Modify: `src/sauspiel_scraper/models.py`
  **Approach:**
  - Add `ProcessedGame` class inheriting from `BaseModel`.
  - Include fields: `game_id`, `date`, `game_type`, `declarer`, `role`, `is_declarer_win`, `is_my_win`, `net_profit_cents`, `laufende`, `location`.
  **Test scenarios:**
  - Test expectation: none -- pure data model.
  **Verification:**
  - Model can be instantiated with valid data.

- U2. **Refactor Processing Logic & Fix Profit Bug**
  **Goal:** Update `process_game_data` to use the new model and fix the logic.
  **Requirements:** R2, R3
  **Files:**
  - Modify: `src/sauspiel_scraper/app/analytics.py`
  **Approach:**
  - Update return type to `list[ProcessedGame]`.
  - Change loop to instantiate `ProcessedGame`.
  - Fix profit calculation:
    - If `role` in `["Spieler", "Partner"]`: `profit = value` if `won` else `-value`.
    - If `role == "Gegenspieler"`: `profit = -value` if `won` else `value`.
  **Test scenarios:**
  - Happy path: Correct profit for declarer (Win/Loss).
  - Happy path: Correct profit for opponent (Win/Loss).
  **Verification:**
  - `process_game_data` returns a list of `ProcessedGame` objects.

- U3. **Add DataFrame Helper and Update UI**
  **Goal:** Ensure Streamlit still works with the new data format.
  **Requirements:** R4, R5
  **Files:**
  - Modify: `src/sauspiel_scraper/app/analytics.py`
  **Approach:**
  - Add `games_to_df(games: list[ProcessedGame]) -> pd.DataFrame`.
  - Inside `games_to_df`, handle sorting by date and cumulative profit calculation.
  - Update `render_analytics` (or its caller in `app/main.py`) to use `games_to_df`.
  **Test scenarios:**
  - Happy path: `games_to_df` returns expected columns and cumulative profit.
  **Verification:**
  - Streamlit app runs and displays data correctly.

- U4. **Update and Expand Tests**
  **Goal:** Verify the new model and the fix.
  **Requirements:** R6
  **Files:**
  - Modify: `tests/test_ui_processing.py`
  **Approach:**
  - Update existing tests to assert against `ProcessedGame` attributes.
  - Add a dedicated test for the opponent profit fix (Characterization test).
  **Test scenarios:**
  - Happy path: Verify `is_my_win` and `net_profit_cents` for all 4 combinations (Role x Outcome).
  **Verification:**
  - `pytest tests/test_ui_processing.py` passes.

---

## System-Wide Impact

- **Type Safety**: Improved type safety in the analytics layer.
- **Data Correctness**: Profit charts will now correctly reflect the user's actual earnings as an opponent.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Breaking Streamlit filters | Ensure `games_to_df` provides all columns previously expected by `render_analytics`. |

---

## Sources & References

- **Origin document:** docs/brainstorms/2026-04-25-architecture-decoupling-requirements.md
- Related code: `src/sauspiel_scraper/app/analytics.py`
