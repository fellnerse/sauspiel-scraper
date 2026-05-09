import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from sauspiel_scraper.app.main import app
from sauspiel_scraper.core import SauspielScraper

# Setup a dummy FERNET_KEY for tests
TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def mock_fernet_key(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", TEST_KEY)
    # Also mock SauspielScraper.login to always succeed in these web tests
    monkeypatch.setattr(SauspielScraper, "login", lambda self: True)


client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Sauspiel Scraper" in response.text
    assert "Welcome, Guest!" in response.text


def test_login_page():
    response = client.get("/login")
    assert response.status_code == 200
    assert "Login" in response.text
    assert '<input type="text" id="username" name="username"' in response.text


def test_login_post():
    response = client.post(
        "/login", data={"username": "testuser", "password": "password"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Welcome, testuser!" in response.text
    assert "username" in client.cookies
    assert client.cookies["username"] == "testuser"


def test_logout():
    # Login first
    client.post("/login", data={"username": "testuser", "password": "password"})
    assert "username" in client.cookies

    # Logout
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert "Welcome, Guest!" in response.text
    assert "username" not in client.cookies
