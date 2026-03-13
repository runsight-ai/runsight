"""Pytest configuration for API tests."""

import os
import tempfile

# Set test env *before* any runsight_api imports (config loads at import time)
os.environ["RUNSIGHT_DB_URL"] = "sqlite:///:memory:"
os.environ["RUNSIGHT_BASE_PATH"] = os.environ.get("RUNSIGHT_BASE_PATH", tempfile.gettempdir())
