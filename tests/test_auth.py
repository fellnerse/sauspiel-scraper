import pytest
from cryptography.fernet import Fernet

from sauspiel_scraper.app.auth import (
    decrypt_password,
    encrypt_password,
    hash_password,
    verify_password,
)

# Setup a dummy FERNET_KEY for tests
TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def mock_fernet_key(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", TEST_KEY)


def test_encryption_decryption_roundtrip():
    password = "secure_password_123"
    encrypted = encrypt_password(password)
    assert encrypted != password
    assert isinstance(encrypted, str)

    decrypted = decrypt_password(encrypted)
    assert decrypted == password


def test_encryption_is_deterministic_per_key():
    # Fernet encryption is actually NOT deterministic (it includes a timestamp and IV)
    # but decryption should always work.
    password = "test"
    encrypted1 = encrypt_password(password)
    encrypted2 = encrypt_password(password)
    assert encrypted1 != encrypted2  # Fernet tokens are different every time
    assert decrypt_password(encrypted1) == password
    assert decrypt_password(encrypted2) == password


def test_missing_fernet_key_raises_error(monkeypatch):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    # We expect an informative error if the key is missing
    with pytest.raises(ValueError, match="FERNET_KEY"):
        encrypt_password("test")


def test_hashing_verification_roundtrip():
    password = "my_dashboard_password"
    hashed = hash_password(password)
    assert hashed != password
    assert ":" in hashed

    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_hashing_is_not_deterministic():
    password = "test"
    hashed1 = hash_password(password)
    hashed2 = hash_password(password)
    assert hashed1 != hashed2
