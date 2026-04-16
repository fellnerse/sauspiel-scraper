# Sauspiel Scraper

Download and archive your Sauspiel game history for local analysis.

## Features
- Secure login using credentials from environment, CLI, or Web UI.
- Exports game metadata, initial hands, and full trick sequences to JSONL.
- Built with Python 3.14, Typer, Streamlit, and Astral `ty`.

## Usage

### CLI

Set credentials in `.env`:
```env
USERNAME=your_username
PASSWORD=your_password
```

Run the scraper:
```bash
uv run sauspiel-scraper --count 10 --output output/games.jsonl
```

Options:
- `--count`, `-c`: Number of games to scrape.
- `--since`, `-s`: Scrape games since date (DD.MM.YYYY).
- `--pretty`: Save as formatted JSON array instead of JSONL.

### Web UI

Launch the Streamlit app:
```bash
uv run streamlit run src/sauspiel_scraper/app.py
```

## Data Format

Games are saved in JSONL format (one JSON object per line) for resilience. Each game contains:
- `game_id`, `url`, `title`, `game_type`
- `players`: List of player names.
- `initial_hands`: Mapping of player name to their 8 starting cards.
- `tricks`: List of 8 tricks, each with a `winner` (player index) and `cards` (list of `"player_index:card_code"`).
- `meta`: Additional info like `date`, `location`, `wert`, etc.
