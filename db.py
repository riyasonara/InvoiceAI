"""Database engine + session setup (SQLAlchemy).

Single source of truth for the connection. `DATABASE_URL` defaults to the
existing SQLite file, but can point at Postgres in production with no code
changes — e.g. DATABASE_URL=postgresql+psycopg://user:pass@host/db
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///invoice.db")

# check_same_thread is a SQLite-only quirk (FastAPI uses multiple threads).
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Base class every ORM model inherits from.
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
