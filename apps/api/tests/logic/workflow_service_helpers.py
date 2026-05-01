"""Shared fixtures and import stubs for WorkflowService behavior tests."""

from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import Mock

import pytest

__all__ = [
    "InputValidationError",
    "WorkflowEntity",
    "WorkflowHasActiveRuns",
    "WorkflowNotFound",
    "WorkflowService",
    "make_run_read_model",
    "make_run_repo",
    "make_workflow_repo",
    "make_workflow_service",
    "run_read_model",
    "run_repo",
    "workflow_repo",
    "workflow_service",
]


_STUBBED_KEYS = [
    "structlog",
    "structlog.contextvars",
    "runsight_core",
    "runsight_core.identity",
    "runsight_core.yaml",
    "runsight_core.yaml.schema",
    "runsight_core.yaml.parser",
    "ruamel",
    "ruamel.yaml",
    "runsight_api.data.filesystem",
    "runsight_api.data.filesystem.workflow_repo",
    "runsight_api.data.repositories",
    "runsight_api.data.repositories.run_repo",
    "runsight_api.logic.services.workflow_service",
]


class _EntityKind:
    SOUL = "soul"
    WORKFLOW = "workflow"
    TOOL = "tool"
    PROVIDER = "provider"
    ASSERTION = "assertion"


class _EntityRef:
    def __init__(self, kind, id):
        self.kind = kind
        self.id = id

    def __str__(self):
        return f"{self.kind}:{self.id}"


class _RunsightWorkflowFile:
    @classmethod
    def model_validate(cls, data):
        return data


class _YAML:
    def __init__(self, *args, **kwargs):
        self.preserve_quotes = False

    def load(self, _content):
        return {}

    def dump(self, _data, _stream):
        return None


class _WorkflowRepository:
    pass


class _RunRepository:
    pass


def _install_import_stubs() -> dict[str, types.ModuleType | None]:
    originals = {key: sys.modules.get(key) for key in _STUBBED_KEYS}

    structlog = types.ModuleType("structlog")
    structlog.contextvars = types.SimpleNamespace(
        bind_contextvars=lambda **kwargs: None,
        unbind_contextvars=lambda *args, **kwargs: None,
    )
    sys.modules["structlog"] = structlog
    sys.modules["structlog.contextvars"] = structlog.contextvars

    runsight_core = types.ModuleType("runsight_core")
    runsight_core.__path__ = []
    identity_pkg = types.ModuleType("runsight_core.identity")
    yaml_pkg = types.ModuleType("runsight_core.yaml")
    yaml_pkg.__path__ = []
    schema_pkg = types.ModuleType("runsight_core.yaml.schema")
    parser_pkg = types.ModuleType("runsight_core.yaml.parser")

    identity_pkg.EntityKind = _EntityKind
    identity_pkg.EntityRef = _EntityRef
    identity_pkg.validate_entity_id = lambda *_args, **_kwargs: None

    schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
    parser_pkg.validate_tool_governance = lambda _: None
    yaml_pkg.schema = schema_pkg
    yaml_pkg.parser = parser_pkg
    runsight_core.identity = identity_pkg
    runsight_core.yaml = yaml_pkg
    sys.modules["runsight_core"] = runsight_core
    sys.modules["runsight_core.identity"] = identity_pkg
    sys.modules["runsight_core.yaml"] = yaml_pkg
    sys.modules["runsight_core.yaml.schema"] = schema_pkg
    sys.modules["runsight_core.yaml.parser"] = parser_pkg

    ruamel = types.ModuleType("ruamel")
    ruamel.__path__ = []
    ruamel_yaml = types.ModuleType("ruamel.yaml")
    ruamel_yaml.YAML = _YAML
    ruamel.yaml = ruamel_yaml
    sys.modules["ruamel"] = ruamel
    sys.modules["ruamel.yaml"] = ruamel_yaml

    fake_filesystem_pkg = types.ModuleType("runsight_api.data.filesystem")
    fake_filesystem_pkg.__path__ = []
    fake_workflow_repo = types.ModuleType("runsight_api.data.filesystem.workflow_repo")
    fake_workflow_repo.WorkflowRepository = _WorkflowRepository
    fake_filesystem_pkg.workflow_repo = fake_workflow_repo
    sys.modules["runsight_api.data.filesystem"] = fake_filesystem_pkg
    sys.modules["runsight_api.data.filesystem.workflow_repo"] = fake_workflow_repo

    fake_repositories_pkg = types.ModuleType("runsight_api.data.repositories")
    fake_repositories_pkg.__path__ = []
    fake_run_repo = types.ModuleType("runsight_api.data.repositories.run_repo")
    fake_run_repo.RunRepository = _RunRepository
    fake_repositories_pkg.run_repo = fake_run_repo
    sys.modules["runsight_api.data.repositories"] = fake_repositories_pkg
    sys.modules["runsight_api.data.repositories.run_repo"] = fake_run_repo

    return originals


def _restore_import_stubs(originals: dict[str, types.ModuleType | None]) -> None:
    for key, original in originals.items():
        if original is not None:
            sys.modules[key] = original
        else:
            sys.modules.pop(key, None)


_originals = _install_import_stubs()
try:
    _errors_module = importlib.import_module("runsight_api.domain.errors")
    _value_objects_module = importlib.import_module("runsight_api.domain.value_objects")
    _workflow_service_module = importlib.import_module(
        "runsight_api.logic.services.workflow_service"
    )
finally:
    _restore_import_stubs(_originals)

InputValidationError = _errors_module.InputValidationError
WorkflowHasActiveRuns = _errors_module.WorkflowHasActiveRuns
WorkflowNotFound = _errors_module.WorkflowNotFound
WorkflowEntity = _value_objects_module.WorkflowEntity
WorkflowService = _workflow_service_module.WorkflowService


def make_workflow_repo():
    return Mock()


def make_run_repo():
    return Mock()


def make_run_read_model():
    mock = Mock()
    mock.get_workflow_health_metrics.return_value = {}
    return mock


def make_workflow_service(workflow_repo, run_repo, run_read_model):
    return WorkflowService(workflow_repo, run_repo, run_read_model=run_read_model)


@pytest.fixture
def workflow_repo():
    return make_workflow_repo()


@pytest.fixture
def run_repo():
    return make_run_repo()


@pytest.fixture
def run_read_model():
    return make_run_read_model()


@pytest.fixture
def workflow_service(workflow_repo, run_repo, run_read_model):
    return make_workflow_service(workflow_repo, run_repo, run_read_model)
