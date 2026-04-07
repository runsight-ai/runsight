"""Pytest configuration for API tests."""

import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Test DB: temp-file SQLite so all connections share the same database.
# :memory: gives each connection its own isolated DB — tables created by
# Alembic or create_all() are invisible to other connections.
# ---------------------------------------------------------------------------
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), f"runsight_test_{os.getpid()}.db")
os.environ["RUNSIGHT_DB_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["RUNSIGHT_BASE_PATH"] = os.environ.get("RUNSIGHT_BASE_PATH", tempfile.gettempdir())


@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    """Create all DB tables once per session, tear down after."""
    from sqlmodel import SQLModel

    from runsight_api.core.di import engine
    from runsight_api.domain import entities as _entities  # noqa: F401 — register models

    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    # Remove the temp DB file
    try:
        os.unlink(_TEST_DB_PATH)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _clear_context_vars():
    """Reset all context vars after each test to prevent cross-test pollution."""
    yield
    from runsight_api.core.context import clear_execution_context, request_id

    clear_execution_context()
    request_id.set("")
