"""Red tests for RUN-478: workflow health metrics on GET /api/workflows.

These tests define the backend behavior needed for workflow health aggregation:
  - WorkflowService must accept a RunRepository dependency
  - list_workflows must aggregate health metrics from runs
  - simulation runs must be excluded from health KPIs
  - zero-run and no-eval edge cases must return sensible health defaults

All tests are expected to fail until the feature is implemented.
"""

import sys
import types
import inspect
from unittest.mock import Mock

import pytest

# The API package imports structlog at module import time, but the current
# local uv environment does not have it installed. Stub it so the red tests can
# reach the intended assertions instead of failing during collection.
if "structlog" not in sys.modules:
    structlog = types.ModuleType("structlog")
    structlog.types = types.SimpleNamespace(Processor=object)
    structlog.contextvars = types.SimpleNamespace(
        bind_contextvars=lambda **kwargs: None,
        unbind_contextvars=lambda *args, **kwargs: None,
        merge_contextvars=lambda *args, **kwargs: None,
    )
    structlog.stdlib = types.SimpleNamespace(
        add_log_level=lambda *args, **kwargs: None,
        add_logger_name=lambda *args, **kwargs: None,
        LoggerFactory=lambda *args, **kwargs: None,
        BoundLogger=object,
        ProcessorFormatter=type(
            "ProcessorFormatter",
            (),
            {
                "__init__": lambda self, *args, **kwargs: None,
                "wrap_for_formatter": staticmethod(lambda *args, **kwargs: None),
                "remove_processors_meta": staticmethod(lambda *args, **kwargs: None),
            },
        ),
    )
    structlog.processors = types.SimpleNamespace(
        TimeStamper=lambda *args, **kwargs: None,
        StackInfoRenderer=lambda *args, **kwargs: None,
        format_exc_info=lambda *args, **kwargs: None,
        JSONRenderer=lambda *args, **kwargs: None,
    )
    structlog.dev = types.SimpleNamespace(ConsoleRenderer=lambda *args, **kwargs: None)
    structlog.configure = lambda *args, **kwargs: None
    sys.modules["structlog"] = structlog
    sys.modules["structlog.types"] = structlog.types
    sys.modules["structlog.contextvars"] = structlog.contextvars
    sys.modules["structlog.stdlib"] = structlog.stdlib
    sys.modules["structlog.processors"] = structlog.processors
    sys.modules["structlog.dev"] = structlog.dev

if "runsight_core" not in sys.modules:
    runsight_core = types.ModuleType("runsight_core")
    runsight_core.__path__ = []

    observer_pkg = types.ModuleType("runsight_core.observer")
    observer_pkg.__path__ = []
    observer_pkg.CompositeObserver = type("CompositeObserver", (), {})
    observer_pkg.LoggingObserver = type("LoggingObserver", (), {})
    observer_pkg.compute_prompt_hash = lambda *args, **kwargs: "prompt-hash"
    observer_pkg.compute_soul_version = lambda *args, **kwargs: "soul-version"

    yaml_pkg = types.ModuleType("runsight_core.yaml")
    yaml_pkg.__path__ = []
    schema_pkg = types.ModuleType("runsight_core.yaml.schema")
    parser_pkg = types.ModuleType("runsight_core.yaml.parser")

    class _RunsightWorkflowFile:
        @classmethod
        def model_validate(cls, data):
            return data

    schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
    parser_pkg.parse_workflow_yaml = lambda *args, **kwargs: {}
    yaml_pkg.parser = parser_pkg
    yaml_pkg.schema = schema_pkg
    runsight_core.yaml = yaml_pkg

    llm_pkg = types.ModuleType("runsight_core.llm")
    llm_pkg.__path__ = []
    llm_model_catalog_pkg = types.ModuleType("runsight_core.llm.model_catalog")
    llm_model_catalog_pkg.LiteLLMModelCatalog = type("LiteLLMModelCatalog", (), {})
    llm_model_catalog_pkg.ModelCatalogPort = type("ModelCatalogPort", (), {})
    llm_model_catalog_pkg.ModelInfo = type("ModelInfo", (), {})
    llm_pkg.model_catalog = llm_model_catalog_pkg
    runsight_core.llm = llm_pkg

    assertions_pkg = types.ModuleType("runsight_core.assertions")
    assertions_pkg.__path__ = []
    assertions_base_pkg = types.ModuleType("runsight_core.assertions.base")
    assertions_registry_pkg = types.ModuleType("runsight_core.assertions.registry")
    assertions_scoring_pkg = types.ModuleType("runsight_core.assertions.scoring")

    class _AssertionContext:
        pass

    class _GradingResult:
        def __init__(self, *args, **kwargs):
            self.passed = kwargs.get("passed", True)
            self.score = kwargs.get("score", 1.0)
            self.reason = kwargs.get("reason")
            self.named_scores = kwargs.get("named_scores", {})
            self.tokens_used = kwargs.get("tokens_used")
            self.component_results = kwargs.get("component_results")
            self.assertion_type = kwargs.get("assertion_type")
            self.metadata = kwargs.get("metadata")

    class _AssertionsResult:
        def __init__(self, *args, **kwargs):
            self.score = 0.0

    assertions_base_pkg.AssertionContext = _AssertionContext
    assertions_base_pkg.GradingResult = _GradingResult
    assertions_registry_pkg.NOT_PREFIX = "not_"
    assertions_registry_pkg._get_handler = lambda *args, **kwargs: type(
        "DummyAssertionHandler",
        (),
        {
            "__init__": lambda self, *a, **k: None,
            "evaluate": lambda self, *a, **k: _GradingResult(),
        },
    )
    assertions_scoring_pkg.AssertionsResult = _AssertionsResult
    assertions_pkg.base = assertions_base_pkg
    assertions_pkg.registry = assertions_registry_pkg
    assertions_pkg.scoring = assertions_scoring_pkg
    runsight_core.assertions = assertions_pkg

    primitives_pkg = types.ModuleType("runsight_core.primitives")
    primitives_pkg.Soul = type("Soul", (), {})
    runsight_core.primitives = primitives_pkg

    state_pkg = types.ModuleType("runsight_core.state")
    state_pkg.BlockResult = type("BlockResult", (), {})
    state_pkg.WorkflowState = type("WorkflowState", (), {})
    runsight_core.state = state_pkg

    runsight_core.observer = observer_pkg
    sys.modules["runsight_core"] = runsight_core
    sys.modules["runsight_core.observer"] = observer_pkg
    sys.modules["runsight_core.yaml"] = yaml_pkg
    sys.modules["runsight_core.yaml.schema"] = schema_pkg
    sys.modules["runsight_core.yaml.parser"] = parser_pkg
    sys.modules["runsight_core.llm"] = llm_pkg
    sys.modules["runsight_core.llm.model_catalog"] = llm_model_catalog_pkg
    sys.modules["runsight_core.assertions"] = assertions_pkg
    sys.modules["runsight_core.assertions.base"] = assertions_base_pkg
    sys.modules["runsight_core.assertions.registry"] = assertions_registry_pkg
    sys.modules["runsight_core.assertions.scoring"] = assertions_scoring_pkg
    sys.modules["runsight_core.primitives"] = primitives_pkg
    sys.modules["runsight_core.state"] = state_pkg

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.logic.services.workflow_service import WorkflowService


def _make_run(
    run_id: str,
    *,
    workflow_id: str = "wf_1",
    source: str = "manual",
    status: str = "completed",
) -> Mock:
    run = Mock()
    run.id = run_id
    run.workflow_id = workflow_id
    run.workflow_name = "Research Flow"
    run.source = source
    run.status = status
    run.branch = "main"
    run.commit_sha = "abc123def456"
    run.workflow_commit_sha = None
    run.created_at = 1711900000.0
    return run


def _make_node(
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None = None,
    eval_score: float | None = None,
) -> Mock:
    node = Mock()
    node.id = f"{run_id}:{node_id}"
    node.run_id = run_id
    node.node_id = node_id
    node.block_type = "llm"
    node.status = "completed"
    node.eval_passed = eval_passed
    node.eval_score = eval_score
    node.soul_id = "soul_1"
    node.soul_version = "v1"
    node.cost_usd = 0.01
    node.tokens = {"total": 100}
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
        manual_run = _make_run("run_manual", source="manual")
        webhook_run = _make_run("run_webhook", source="webhook")
        simulation_run = _make_run("run_sim", source="simulation")
        run_repo.list_runs.return_value = [manual_run, webhook_run, simulation_run]

        nodes_by_run = {
            "run_manual": [_make_node("run_manual", "node_a", eval_passed=True, eval_score=0.9)],
            "run_webhook": [_make_node("run_webhook", "node_b", eval_passed=False, eval_score=0.2)],
            "run_sim": [_make_node("run_sim", "node_sim", eval_passed=True, eval_score=1.0)],
        }
        run_repo.list_nodes_for_run.side_effect = lambda run_id: nodes_by_run[run_id]

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.list_runs.assert_called_once()
        assert run_repo.list_nodes_for_run.call_count >= 2

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 2
        assert _health_value(health, "eval_health") == pytest.approx(0.5)
        threshold = _health_value(health, "eval_health_threshold")
        assert threshold is not None
        assert 0.0 <= threshold <= 1.0

    def test_list_workflows_returns_zero_health_for_no_runs(self):
        """A workflow with no runs should still return an explicit zero-health payload."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_empty", name="Empty Flow")]

        run_repo = Mock()
        run_repo.list_runs.return_value = []

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        run_repo.list_runs.assert_called_once()
        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 0
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_health_threshold") is None

    def test_list_workflows_returns_null_eval_health_when_no_eval_data(self):
        """A workflow with runs but no eval data should not invent an eval score."""
        workflow_repo = Mock()
        workflow_repo.list_all.return_value = [WorkflowEntity(id="wf_no_eval", name="No Eval Flow")]

        run_repo = Mock()
        run_repo.list_runs.return_value = [_make_run("run_1", source="manual")]
        run_repo.list_nodes_for_run.return_value = [
            _make_node("run_1", "node_a", eval_passed=None, eval_score=None)
        ]

        service = WorkflowService(workflow_repo)
        service.run_repo = run_repo

        result = service.list_workflows()

        health = _workflow_health(result[0])
        assert _health_value(health, "run_count") == 1
        assert _health_value(health, "eval_health") is None
        assert _health_value(health, "eval_health_threshold") is None
