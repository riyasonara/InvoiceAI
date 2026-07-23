"""Symmetric encryption for secrets at rest (OAuth tokens).

Uses Fernet with FERNET_KEY from .env. Tokens are encrypted before they ever
touch the database and decrypted only in memory when a Gmail call is made.
"""
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

_key = os.getenv("FERNET_KEY")
_fernet = Fernet(_key.encode()) if _key else None


def encrypt(plaintext):
    """Encrypt a string; returns None for None (so optional tokens pass through)."""
    if plaintext is None:
        return None
    if _fernet is None:
        raise RuntimeError("FERNET_KEY is not configured.")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext):
    """Decrypt a string produced by encrypt(); returns None for None."""
    if ciphertext is None:
        return None
    if _fernet is None:
        raise RuntimeError("FERNET_KEY is not configured.")
    return _fernet.decrypt(ciphertext.encode()).decode()
