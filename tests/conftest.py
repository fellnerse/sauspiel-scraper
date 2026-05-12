import pytest
from cryptography.fernet import Fernet

# Setup a dummy FERNET_KEY for tests
TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure tests always use a fresh SQLite database and have a FERNET_KEY."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FERNET_KEY", TEST_KEY)
