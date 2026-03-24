"""Pytest configuration for API tests."""

import os
import tempfile

import pytest

# Set test env *before* any runsight_api imports (config loads at import time)
os.environ["RUNSIGHT_DB_URL"] = "sqlite:///:memory:"
os.environ["RUNSIGHT_BASE_PATH"] = os.environ.get("RUNSIGHT_BASE_PATH", tempfile.gettempdir())


@pytest.fixture(autouse=True)
def _clear_context_vars():
    """Reset all context vars after each test to prevent cross-test pollution."""
    yield
    from runsight_api.core.context import clear_execution_context, request_id

    clear_execution_context()
    request_id.set("")
