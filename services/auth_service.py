import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

# Load JWT_SECRET (and the rest of .env) so this module is self-contained.
load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password):
    """Turn a plaintext password into a one-way, salted bcrypt hash.

    bcrypt.gensalt() creates a fresh random salt each time, so two users with
    the same password still get different hashes. We store the result as a
    string (bcrypt hashes are ASCII-safe).
    """
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")


def verify_password(password, hashed_password):
    """Check a plaintext password against a stored bcrypt hash.

    bcrypt re-reads the salt embedded in the stored hash, hashes the given
    password the same way, and compares. Returns True on a match.
    """
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id):
    """Create a signed JWT that proves the caller is this user.

    The token carries the user id in "sub" (subject) and an "exp" expiry.
    It is signed with JWT_SECRET using HS256, so nobody without the secret
    can forge or tamper with it.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
