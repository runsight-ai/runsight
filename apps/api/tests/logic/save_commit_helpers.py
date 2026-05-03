"""Shared fixtures for save commit policy tests."""

from __future__ import annotations

import importlib
from unittest.mock import Mock

import pytest


for module_name in (
    "runsight_core",
    "runsight_core.llm",
    "runsight_core.llm.model_catalog",
    "runsight_core.observer",
    "runsight_core.yaml",
    "runsight_core.yaml.parser",
):
    importlib.import_module(module_name)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_service():
    svc = Mock()
    svc.current_branch.return_value = "main"
    svc.is_clean.return_value = False
    return svc


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def soul_repo():
    return Mock()


# ---------------------------------------------------------------------------
# 1. WorkflowService — create triggers git commit
# ---------------------------------------------------------------------------
