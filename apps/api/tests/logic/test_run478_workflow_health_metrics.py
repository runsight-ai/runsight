"""Red tests for RUN-478: workflow health metrics on GET /api/workflows."""

# ruff: noqa: E402

import sys
import types
from unittest.mock import Mock

import pytest

_STUBBED_KEYS = [
    "structlog",
    "structlog.contextvars",
    "runsight_core",
    "runsight_core.identity",
    "runsight_core.yaml",
    "runsight_core.yaml.schema",
    "runsight_api.data.filesystem",
    "runsight_api.data.filesystem.workflow_repo",
    "runsight_api.data.repositories",
    "runsight_api.data.repositories.run_repo",
]
_originals = {key: sys.modules.get(key) for key in _STUBBED_KEYS}

structlog = types.ModuleType("structlog")
structlog.contextvars = types.SimpleNamespace(
    bind_contextvars=lambda **kwargs: None,
    unbind_contextvars=lambda *args, **kwargs: None,
)
sys.modules["structlog"] = structlog
sys.modules["structlog.contextvars"] = structlog.contextvars

runsight_core = types.ModuleType("runsight_core")
runsight_core.__path__ = []
yaml_pkg = types.ModuleType("runsight_core.yaml")
yaml_pkg.__path__ = []
identity_pkg = types.ModuleType("runsight_core.identity")
schema_pkg = types.ModuleType("runsight_core.yaml.schema")


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


identity_pkg.EntityKind = _EntityKind
identity_pkg.EntityRef = _EntityRef
identity_pkg.validate_entity_id = lambda *_args, **_kwargs: None


class _RunsightWorkflowFile:
    @classmethod
    def model_validate(cls, data):
        return data


schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
yaml_pkg.schema = schema_pkg
runsight_core.identity = identity_pkg
runsight_core.yaml = yaml_pkg
sys.modules["runsight_core"] = runsight_core
sys.modules["runsight_core.identity"] = identity_pkg
sys.modules["runsight_core.yaml"] = yaml_pkg
sys.modules["runsight_core.yaml.schema"] = schema_pkg

fake_filesystem_pkg = types.ModuleType("runsight_api.data.filesystem")
fake_filesystem_pkg.__path__ = []
fake_workflow_repo = types.ModuleType("runsight_api.data.filesystem.workflow_repo")


class _WorkflowRepository:
    pass


fake_workflow_repo.WorkflowRepository = _WorkflowRepository
fake_filesystem_pkg.workflow_repo = fake_workflow_repo
sys.modules["runsight_api.data.filesystem"] = fake_filesystem_pkg
sys.modules["runsight_api.data.filesystem.workflow_repo"] = fake_workflow_repo

fake_repositories_pkg = types.ModuleType("runsight_api.data.repositories")
fake_repositories_pkg.__path__ = []
fake_run_repo = types.ModuleType("runsight_api.data.repositories.run_repo")


class _RunRepository:
    pass


fake_run_repo.RunRepository = _RunRepository
fake_repositories_pkg.run_repo = fake_run_repo
sys.modules["runsight_api.data.repositories"] = fake_repositories_pkg
sys.modules["runsight_api.data.repositories.run_repo"] = fake_run_repo

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService

for _key, _orig in _originals.items():
    if _orig is not None:
        sys.modules[_key] = _orig
    else:
        sys.modules.pop(_key, None)


def _make_run(
    run_id: str,
    *,
    workflow_id: str = "wf_1",
    source: str = "manual",
) -> Mock:
    run = Mock()
    run.id = run_id
    run.workflow_id = workflow_id
    run.workflow_name = "Research Flow"
    run.source = source
    return run


def _make_workflow_health(
    *,
    eval_health: str | None,
    run_count: int,
    eval_pass_pct: float | None,
    total_cost_usd: float,
    regression_count: int,
) -> dict:
    return {
        "eval_health": eval_health,
        "run_count": run_count,
        "eval_pass_pct": eval_pass_pct,
        "total_cost_usd": total_cost_usd,
        "regression_count": regression_count,
    }


def _workflow_health(item):
    health = getattr(item, "health", None) or getattr(item, "health_metrics", None)
    assert health is not None, "Expected workflow health metadata to be present"
    return health


def _health_value(health, name: str):
    if isinstance(health, dict):
        return health.get(name)
    return getattr(health, name, None)


class TestWorkflowHealthAggregation:
    def test_list_workflows_aggregates_health(self):
        """WorkflowService should expose aggregated workflow health metadata."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [
            WorkflowEntity(kind="workflow", id="wf_1", name="Research Flow")
        ]

        run_repo = Mock()
        run_repo.get_workflow_health_metrics.return_value = {
            "wf_1": _make_workflow_health(
                eval_health="danger",
                run_count=2,
                eval_pass_pct=50.0,
                total_cost_usd=0.30,
                regression_count=1,
            )
        }

        service = WorkflowService(workflow_repo, run_repo)

        result = service.list_workflows()

        run_repo.get_workflow_health_metrics.assert_called_once()
        run_repo.list_nodes_for_run.assert_not_called()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 2
        assert _health_value(health, "eval_health") == "danger"
        assert _health_value(health, "eval_pass_pct") == 50.0
        assert _health_value(health, "total_cost_usd") == pytest.approx(0.30)
        assert _health_value(health, "regression_count") == 1

    def test_list_workflows_handles_zero_run_edge_case(self):
        """A workflow with no runs should still expose zeroed health fields."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [
            WorkflowEntity(kind="workflow", id="wf_empty", name="Empty Flow")
        ]

        run_repo = Mock()
        run_repo.get_workflow_health_metrics.return_value = {
            "wf_empty": _make_workflow_health(
                eval_health=None,
                run_count=0,
                eval_pass_pct=None,
                total_cost_usd=0.0,
                regression_count=0,
            )
        }

        service = WorkflowService(workflow_repo, run_repo)

        result = service.list_workflows()

        run_repo.get_workflow_health_metrics.assert_called_once()
        run_repo.list_nodes_for_run.assert_not_called()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 0
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_pass_pct") is None
        assert _health_value(health, "total_cost_usd") == 0.0
        assert _health_value(health, "regression_count") == 0

    def test_list_workflows_handles_no_eval_edge_case(self):
        """A workflow with runs but no eval data should not invent percentages."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [
            WorkflowEntity(kind="workflow", id="wf_no_eval", name="No Eval Flow")
        ]

        run_repo = Mock()
        run_repo.get_workflow_health_metrics.return_value = {
            "wf_no_eval": _make_workflow_health(
                eval_health=None,
                run_count=1,
                eval_pass_pct=None,
                total_cost_usd=0.25,
                regression_count=0,
            )
        }

        service = WorkflowService(workflow_repo, run_repo)

        result = service.list_workflows()

        run_repo.get_workflow_health_metrics.assert_called_once()
        run_repo.list_nodes_for_run.assert_not_called()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 1
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_pass_pct") is None
        assert _health_value(health, "total_cost_usd") == pytest.approx(0.25)
        assert _health_value(health, "regression_count") == 0
