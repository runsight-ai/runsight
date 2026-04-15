"""
RUN-858 — Orphan removal: /api/tasks and /api/steps must not exist.

Red tests: assert the routes return 404 and the router files are gone.
These fail while the routers are still registered.
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app

client = TestClient(app, raise_server_exceptions=False)

TASKS_ROUTER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "src",
    "runsight_api",
    "transport",
    "routers",
    "tasks.py",
)
STEPS_ROUTER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "src",
    "runsight_api",
    "transport",
    "routers",
    "steps.py",
)


class TestOrphanedRoutersRemoved:
    def test_get_tasks_returns_404(self):
        """GET /api/tasks must not exist after RUN-858 cleanup."""
        response = client.get("/api/tasks")
        assert response.status_code == 404, (
            f"Expected 404 (route removed) but got {response.status_code}. "
            "The /api/tasks router is still registered."
        )

    def test_get_steps_returns_404(self):
        """GET /api/steps must not exist after RUN-858 cleanup."""
        response = client.get("/api/steps")
        assert response.status_code == 404, (
            f"Expected 404 (route removed) but got {response.status_code}. "
            "The /api/steps router is still registered."
        )

    def test_tasks_router_file_does_not_exist(self):
        """tasks.py router file must be deleted from disk."""
        assert not os.path.exists(os.path.normpath(TASKS_ROUTER_PATH)), (
            f"Router file still exists: {TASKS_ROUTER_PATH}"
        )

    def test_steps_router_file_does_not_exist(self):
        """steps.py router file must be deleted from disk."""
        assert not os.path.exists(os.path.normpath(STEPS_ROUTER_PATH)), (
            f"Router file still exists: {STEPS_ROUTER_PATH}"
        )

    def test_tasks_module_is_not_importable(self):
        """runsight_api.transport.routers.tasks must not be importable."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("runsight_api.transport.routers.tasks")

    def test_steps_module_is_not_importable(self):
        """runsight_api.transport.routers.steps must not be importable."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("runsight_api.transport.routers.steps")
