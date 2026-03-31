"""Red tests for RUN-478: workflow health metrics on GET /api/workflows."""

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
    def test_list_workflows_aggregates_health_and_excludes_simulations(self):
        """Simulation runs must not affect workflow health KPIs."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_1", name="Research Flow")]

        run_repo = Mock()
        run_repo.aggregate_workflow_health.return_value = {
            "wf_1": _make_workflow_health(
                eval_health="warning",
                run_count=2,
                eval_pass_pct=50.0,
                total_cost_usd=0.30,
                regression_count=1,
            )
        }

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.aggregate_workflow_health.assert_called_once()
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
        run_repo.aggregate_workflow_health.return_value = {
            "wf_empty": _make_workflow_health(
                eval_health=None,
                run_count=0,
                eval_pass_pct=None,
                total_cost_usd=0.0,
                regression_count=0,
            )
        }

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.aggregate_workflow_health.assert_called_once()
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
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_no_eval", name="No Eval Flow")]

        run_repo = Mock()
        run_repo.aggregate_workflow_health.return_value = {
            "wf_no_eval": _make_workflow_health(
                eval_health=None,
                run_count=1,
                eval_pass_pct=None,
                total_cost_usd=0.25,
                regression_count=0,
            )
        }

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.aggregate_workflow_health.assert_called_once()
        run_repo.list_nodes_for_run.assert_not_called()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 1
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_pass_pct") is None
        assert _health_value(health, "total_cost_usd") == pytest.approx(0.25)
        assert _health_value(health, "regression_count") == 0
