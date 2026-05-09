import hashlib
import os
import secrets

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    key = os.getenv("FERNET_KEY")
    if not key:
        raise ValueError("FERNET_KEY environment variable is not set")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise ValueError(f"Invalid FERNET_KEY: {e}") from e


def encrypt_password(password: str) -> str:
    """
    Encrypts a password string using Fernet symmetric encryption.
    Returns a URL-safe base64 string.
    """
    f = _get_fernet()
    token = f.encrypt(password.encode())
    return token.decode()


def decrypt_password(token: str) -> str:
    """
    Decrypts a Fernet token back to the original password string.
    """
    f = _get_fernet()
    password = f.decrypt(token.encode() if isinstance(token, str) else token)
    return password.decode()


def hash_password(password: str) -> str:
    """
    Hashes a password with a random salt for secure storage.
    Format: salt:hash
    """
    salt = secrets.token_hex(16)
    hash_value = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hash_value}"


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a password against a salt:hash string.
    """
    try:
        salt, stored_hash = hashed_password.split(":")
        new_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return new_hash == stored_hash
    except ValueError:
        return False
