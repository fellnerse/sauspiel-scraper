# Requirements: Architecture Decoupling & Profit Logic Fix

Introduce a Pydantic model for processed game data to improve testability and fix a bug in profit calculation for opponents.

## Goals
- Decouple data processing from Pandas/Streamlit by using a Pydantic model as the intermediate format.
- Fix the profit calculation logic: if the user is an opponent and the declarer loses, the user's profit should be positive.
- Enable comprehensive unit testing of the processing logic.

## Proposed Model: `ProcessedGame`
Location: `src/sauspiel_scraper/models.py`

Fields:
- `game_id`: str
- `date`: datetime
- `game_type`: str
- `declarer`: str
- `role`: str ("Spieler", "Partner", "Gegenspieler")
- `is_declarer_win`: bool
- `is_my_win`: bool
- `net_profit_cents`: int (Personal profit/loss for the user)
- `laufende`: int
- `location`: str

## Logic Changes
- **Profit Calculation**:
  - If `role` in `["Spieler", "Partner"]`: `profit = value` if `won` else `-value`.
  - If `role == "Gegenspieler"`: `profit = -value` if `won` else `value`.
- **Return Type**: `process_game_data` will now return `list[ProcessedGame]`.
- **Compatibility**: A helper function `games_to_df(games: list[ProcessedGame]) -> pd.DataFrame` will be provided for the UI layer.

## Testing Strategy
- Update `tests/test_ui_processing.py` to use the new return type.
- Add test cases for different roles (Declarer vs Opponent) and outcomes (Won vs Lost) to verify `net_profit_cents`.
- Verify cumulative profit calculation in the DataFrame conversion.

## Scope Boundaries
- **In Scope**: `src/sauspiel_scraper/models.py`, `src/sauspiel_scraper/app/analytics.py`, `tests/test_ui_processing.py`.
- **Out of Scope**: Splitting `analytics.py` into multiple files (per user preference).
