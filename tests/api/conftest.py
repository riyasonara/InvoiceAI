"""Shared pytest fixtures: a real, isolated Postgres test database.

Every service in this app opens its own SQLAlchemy session (SessionLocal()
directly, not FastAPI's Depends(get_db)) and commits it immediately — so the
usual "wrap each test in one rolled-back transaction" trick has no single
session to attach to. Instead: point DATABASE_URL at a dedicated test
database for the whole run, build its schema from the real Alembic
migrations, and truncate every table before each test.
"""
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
if "test" not in TEST_DATABASE_URL.lower():
    raise RuntimeError(
        "TEST_DATABASE_URL does not contain 'test' — refusing to run tests "
        "against what might be the real database."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SYNC_INTERVAL_SECONDS"] = "0"  # don't let the Gmail scheduler run during tests
os.environ["RATE_LIMIT_ENABLED"] = "false"  # tests hit /login etc. far faster than any human

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import db  # noqa: E402
from main import app  # noqa: E402

TABLES = (
    "invoice_processing_logs",
    "email_attachments",
    "email_messages",
    "email_accounts",
    "invoices",
    "users",
    "organizations",
)


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    """Build the test database's schema from the real migrations, once per run."""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_database():
    """Wipe every table before each test, so tests never see leftovers —
    including from a previous test that failed mid-way."""
    with db.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def register_org():
    """Factory: register + log in as a brand-new user, each in their OWN
    TestClient (own cookie jar), so a test can hold two different
    organizations' logged-in sessions side by side."""
    def _register(email, password, *, organization_name=None, invite_code=None):
        payload = {"email": email, "password": password}
        if organization_name:
            payload["organization_name"] = organization_name
        if invite_code:
            payload["invite_code"] = invite_code
        c = TestClient(app)
        c.post("/register", json=payload)
        c.post("/login", json={"email": email, "password": password})
        return c
    return _register
