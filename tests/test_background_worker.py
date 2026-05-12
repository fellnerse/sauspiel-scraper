from contextlib import contextmanager

from fastapi.testclient import TestClient

from sauspiel_scraper.app.main import app, scheduler

client = TestClient(app)


def test_scheduler_initialized():
    """Verify that the scheduler is part of the app state and running."""
    assert scheduler is not None
    # We can't easily check if it's "running" without starting the app,
    # but we can check if it exists.
    assert hasattr(scheduler, "start")


def test_scrape_endpoint_requires_login():
    """The /scrape endpoint should return 401 if not logged in."""
    response = client.post("/scrape")
    assert response.status_code == 401


def test_scrape_endpoint_triggers_job(monkeypatch):
    """The /scrape endpoint should trigger a scrape for the logged-in user."""
    added_jobs = []

    def mock_add_job(func, *args, **kwargs):
        added_jobs.append((func, args, kwargs))

    # Mocking the scheduler to avoid real background execution
    import sauspiel_scraper.app.main as main

    monkeypatch.setattr(main.scheduler, "add_job", mock_add_job)
    # Mock scraper login to allow logging in
    monkeypatch.setattr("sauspiel_scraper.core.SauspielScraper.login", lambda self: True)

    # Log in first to get a signed session cookie
    client.post("/login", data={"username": "testuser", "password": "password"})

    response = client.post("/scrape")
    assert response.status_code == 200
    assert "Scrape triggered" in response.text

    assert len(added_jobs) == 1


def test_scrape_all_users_logic(monkeypatch):
    """Verify the logic of scrape_all_users function."""
    # Mock data
    mock_user = {
        "username": "testuser",
        "encrypted_password": "encrypted_secret",
        "last_scraped_at": None,
    }

    # Track calls
    db_calls = []
    scraper_calls = []

    class MockDB:
        @contextmanager
        def session_scope(self):
            yield "mock_session"

        def get_all_users(self, session=None):
            return ["testuser"]

        def get_user(self, username, session=None):
            db_calls.append(("get_user", username))
            return mock_user

        def save_game(self, game, session=None):
            db_calls.append(("save_game", game.game_id))

        def update_last_scraped(self, username, ts, session=None):
            db_calls.append(("update_last_scraped", username, ts))

        def game_exists(self, gid, session=None):
            return False

    class MockScraper:
        def __init__(self, username, password, **kwargs):
            scraper_calls.append(("init", username, password))
            self.username = username

        def login(self):
            scraper_calls.append(("login", self.username))
            return True

        def get_game_list_paginated(self, **kwargs):
            from datetime import datetime

            from sauspiel_scraper.models import GamePreview

            return [GamePreview(game_id="123", date=datetime.now())]

        def scrape_game(self, gid, preview):
            from datetime import datetime

            from sauspiel_scraper.models import Game, GameMeta

            return Game(
                game_id=gid, url="http://test", title="Solo", meta=GameMeta(date=datetime.now())
            )

    # Mock dependencies
    import sauspiel_scraper.app.main as main

    monkeypatch.setattr(main, "db", MockDB())
    monkeypatch.setattr(main, "SauspielScraper", MockScraper)
    monkeypatch.setattr(main, "decrypt_password", lambda x: f"decrypted_{x}")

    # Run the function
    main.scrape_all_users()

    # Verify calls
    assert ("get_user", "testuser") in db_calls
    assert ("init", "testuser", "decrypted_encrypted_secret") in scraper_calls
    assert ("login", "testuser") in scraper_calls
    assert ("save_game", "123") in db_calls
    assert any(c[0] == "update_last_scraped" and c[1] == "testuser" for c in db_calls)
