import pytest


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Ensure tests always use a fresh SQLite database by removing DATABASE_URL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
