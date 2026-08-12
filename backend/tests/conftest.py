"""Pytest fixtures: path setup + DB availability detection.

The suite is split into:
- pure unit tests (engine loop, agents, guardrails, chunking) that never touch
  a database and always run;
- API tests that use the live Postgres configured in ``env``/``.env`` and are
  skipped automatically when the database is unreachable (CI without Postgres).
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest


def db_available() -> bool:
    try:
        from app.core.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def schema_present() -> bool:
    """True when the core application tables exist in the connected database.

    CI provides a fresh (empty) Postgres service: the connection succeeds but
    no migrations are applied, so db/api tests would fail on missing tables.
    Treat an unmigrated database like an unavailable one and skip them.
    """
    if not DB_AVAILABLE:
        return False
    try:
        from app.core.database import engine
        from sqlalchemy import inspect

        tables = set(inspect(engine).get_table_names())
        return {"organizations", "users", "integrations"} <= tables
    except Exception:
        return False


DB_AVAILABLE = db_available()
DB_SCHEMA_PRESENT = schema_present()


@pytest.fixture()
def db():
    if not DB_SCHEMA_PRESENT:
        pytest.skip("database schema not available")
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def pytest_collection_modifyitems(config, items):
    """Skip API/db tests early when Postgres is unavailable or unmigrated."""
    if DB_SCHEMA_PRESENT:
        return
    reason = (
        "database unavailable"
        if not DB_AVAILABLE
        else "database schema not migrated; skipping db tests"
    )
    for item in items:
        if "db" in item.keywords or "api" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=reason))


