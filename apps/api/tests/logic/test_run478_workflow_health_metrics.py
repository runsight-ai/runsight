"""Red tests for RUN-478: workflow health metrics on GET /api/workflows."""

import inspect
import sys
import types
from unittest.mock import Mock

import pytest

if "structlog" not in sys.modules:
    structlog = types.ModuleType("structlog")
    structlog.contextvars = types.SimpleNamespace(
        bind_contextvars=lambda **kwargs: None,
        unbind_contextvars=lambda *args, **kwargs: None,
    )
    sys.modules["structlog"] = structlog
    sys.modules["structlog.contextvars"] = structlog.contextvars

if "runsight_core" not in sys.modules:
    runsight_core = types.ModuleType("runsight_core")
    runsight_core.__path__ = []

    yaml_pkg = types.ModuleType("runsight_core.yaml")
    yaml_pkg.__path__ = []
    schema_pkg = types.ModuleType("runsight_core.yaml.schema")

    class _RunsightWorkflowFile:
        @classmethod
        def model_validate(cls, data):
            return data

    schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
    yaml_pkg.schema = schema_pkg
    runsight_core.yaml = yaml_pkg
    sys.modules["runsight_core"] = runsight_core
    sys.modules["runsight_core.yaml"] = yaml_pkg
    sys.modules["runsight_core.yaml.schema"] = schema_pkg

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService


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


def _make_node(
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None = None,
    eval_score: float | None = None,
    total_cost_usd: float = 0.0,
) -> Mock:
    node = Mock()
    node.id = f"{run_id}:{node_id}"
    node.run_id = run_id
    node.node_id = node_id
    node.eval_passed = eval_passed
    node.eval_score = eval_score
    node.cost_usd = total_cost_usd
    node.tokens = {"total": 100}
    node.soul_id = "soul_1"
    node.soul_version = "v1"
    return node


def _workflow_health(item):
    health = getattr(item, "health", None) or getattr(item, "health_metrics", None)
    assert health is not None, "Expected workflow health metadata to be present"
    return health


def _health_value(health, name: str):
    if isinstance(health, dict):
        return health.get(name)
    return getattr(health, name, None)


class TestWorkflowServiceDI:
    def test_workflow_service_signature_includes_run_repo(self):
        """WorkflowService constructor must accept a RunRepository dependency."""
        sig = inspect.signature(WorkflowService)
        assert "run_repo" in sig.parameters, (
            f"WorkflowService is missing a run_repo parameter: {list(sig.parameters)}"
        )


class TestWorkflowHealthAggregation:
    def test_list_workflows_aggregates_health_and_excludes_simulations(self):
        """Simulation runs must not affect workflow health KPIs."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_1", name="Research Flow")]

        run_repo = Mock()
        run_repo.list_runs.return_value = [
            _make_run("run_manual", source="manual"),
            _make_run("run_webhook", source="webhook"),
            _make_run("run_sim", source="simulation"),
        ]
        run_repo.list_nodes_for_run.side_effect = AssertionError(
            "N+1 query detected: workflow health should use a single aggregated query"
        )

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.list_runs.assert_called_once()
        run_repo.list_nodes_for_run.assert_not_called()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 2
        assert _health_value(health, "eval_health") is not None
        assert _health_value(health, "eval_pass_pct") == 50.0
        assert _health_value(health, "total_cost_usd") == pytest.approx(0.30)
        assert _health_value(health, "regression_count") == 1

    def test_list_workflows_handles_zero_run_edge_case(self):
        """A workflow with no runs should still expose zeroed health fields."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_empty", name="Empty Flow")]

        run_repo = Mock()
        run_repo.list_runs.return_value = []

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 0
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_pass_pct") is None
        assert _health_value(health, "total_cost_usd") == 0.0
        assert _health_value(health, "regression_count") == 0

    def test_list_workflows_handles_no_eval_edge_case(self):
        """A workflow with runs but no eval data should not invent percentages."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_no_eval", name="No Eval Flow")]

        run_repo = Mock()
        run_repo.list_runs.return_value = [_make_run("run_1", source="manual")]
        run_repo.list_nodes_for_run.return_value = [
            _make_node("run_1", "node_a", eval_passed=None, eval_score=None, total_cost_usd=0.25)
        ]

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 1
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_pass_pct") is None
        assert _health_value(health, "total_cost_usd") == pytest.approx(0.25)
        assert _health_value(health, "regression_count") == 0
