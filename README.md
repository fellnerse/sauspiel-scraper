# Sauspiel Scraper

Download and archive your Sauspiel game history for local analysis.

## Features
- Secure login using credentials from environment or CLI prompts.
- Exports game metadata, initial hands, and full trick sequences to JSON.
- Built with Python 3.14, Typer, and Astral `ty`.

## Usage

Set credentials in `.env`:
```env
USERNAME=your_username
PASSWORD=your_password
```

Run the scraper:
```bash
uv run sauspiel-scraper --count 10 --output output/games.json
```
