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
nix develop --command uv run sauspiel-scraper --count 10
```

### Web UI

The Web UI is built with FastAPI and HTMX. Launch it with:
```bash
nix develop --command sauspiel-web
```

## Development

This project uses a Nix flake for its development environment, which includes Python 3.14, Docker, and Colima.

### 1. Start Docker environment
On macOS, start Colima and then the PostgreSQL container:
```bash
nix develop --command colima start
nix develop --command docker compose up -d
```

### 2. Database Migrations
Initialize or upgrade the PostgreSQL database:
```bash
nix develop --command bash -c "export \$(grep -v '^#' .env | xargs) && uv run alembic upgrade head"
```

### 3. Migrate Local Data (Optional)
If you have an existing `output/sauspiel.db` (SQLite), you can migrate it to PostgreSQL:
```bash
nix develop --command bash -c "export \$(grep -v '^#' .env | xargs) && uv run python scripts/migrate_sqlite_to_postgres.py"
```

## Data Format

Games are saved in JSONL format (one JSON object per line) for resilience. Each game contains:
- `game_id`, `url`, `title`, `game_type`
- `players`: List of player names.
- `initial_hands`: Mapping of player name to their 8 starting cards.
- `tricks`: List of 8 tricks, each with a `winner` (player index) and `cards` (list of `"player_index:card_code"`).
- `meta`: Additional info like `date`, `location`, `wert`, etc.
