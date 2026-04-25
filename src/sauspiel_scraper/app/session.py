import json
from pathlib import Path

from sauspiel_scraper.core import SauspielScraper

SESSION_FILE = Path("output/session.json")


def save_session(scraper: SauspielScraper) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(scraper.get_session_data(), f)


def load_stored_session() -> SauspielScraper | None:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
            scraper = SauspielScraper()
            scraper.load_session_data(data)
            if scraper.is_logged_in():
                return scraper
        except Exception:
            pass
    return None
