"""Red tests for RUN-478: workflow health metrics on GET /api/workflows.

These tests cover the response contract exposed by the workflows router:
  - new workflow health response fields
  - backward compatibility of existing workflow fields
  - GET /api/workflows should serialize health metadata
  - dependency wiring for the workflows service

All tests are expected to fail until the implementation is added.
"""

import inspect
import sys
import types
from unittest.mock import Mock

import pytest

# The API package imports a handful of third-party modules at import time.
# The current local uv environment does not have all of them available, so we
# provide minimal stubs to let the red tests collect and reach the intended
# assertions.
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

    yaml_pkg = types.ModuleType("runsight_core.yaml")
    yaml_pkg.__path__ = []
    yaml_schema_pkg = types.ModuleType("runsight_core.yaml.schema")
    yaml_parser_pkg = types.ModuleType("runsight_core.yaml.parser")

    class _RunsightWorkflowFile:
        @classmethod
        def model_validate(cls, data):
            return data

    yaml_schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
    yaml_parser_pkg.parse_workflow_yaml = lambda *args, **kwargs: {}
    yaml_pkg.schema = yaml_schema_pkg
    yaml_pkg.parser = yaml_parser_pkg

    llm_pkg = types.ModuleType("runsight_core.llm")
    llm_pkg.__path__ = []
    llm_model_catalog_pkg = types.ModuleType("runsight_core.llm.model_catalog")
    llm_model_catalog_pkg.LiteLLMModelCatalog = type("LiteLLMModelCatalog", (), {})
    llm_model_catalog_pkg.ModelCatalogPort = type("ModelCatalogPort", (), {})
    llm_pkg.model_catalog = llm_model_catalog_pkg

    runsight_core.observer = observer_pkg
    runsight_core.yaml = yaml_pkg
    runsight_core.llm = llm_pkg

    sys.modules["runsight_core"] = runsight_core
    sys.modules["runsight_core.observer"] = observer_pkg
    sys.modules["runsight_core.yaml"] = yaml_pkg
    sys.modules["runsight_core.yaml.schema"] = yaml_schema_pkg
    sys.modules["runsight_core.yaml.parser"] = yaml_parser_pkg
    sys.modules["runsight_core.llm"] = llm_pkg
    sys.modules["runsight_core.llm.model_catalog"] = llm_model_catalog_pkg

if "sqlmodel" not in sys.modules:
    sqlmodel = types.ModuleType("sqlmodel")

    def _field(*args, **kwargs):
        default_factory = kwargs.get("default_factory")
        if callable(default_factory):
            return default_factory()
        return kwargs.get("default")

    class _SQLModel:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

    class _Session:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            return None

    sqlmodel.Session = _Session
    sqlmodel.select = lambda *args, **kwargs: None
    sqlmodel.create_engine = lambda *args, **kwargs: None
    sqlmodel.func = types.SimpleNamespace(count=lambda *args, **kwargs: None)
    sqlmodel.Field = _field
    sqlmodel.Column = lambda *args, **kwargs: None
    sqlmodel.JSON = object()
    sqlmodel.SQLModel = _SQLModel
    sys.modules["sqlmodel"] = sqlmodel

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.transport.deps import get_workflow_service
from runsight_api.transport.routers.workflows import list_workflows
from runsight_api.transport.schemas.workflows import WorkflowResponse


def _make_workflow(
    workflow_id: str = "wf_1",
    *,
    name: str = "Research Flow",
    description: str = "Research workflow",
    yaml: str = "workflow:\n  name: Research Flow\n",
    valid: bool = True,
    validation_error: str | None = None,
    block_count: int = 7,
    modified_at: float = 1711900000.0,
    enabled: bool = True,
    commit_sha: str = "abc123def456",
    health_metrics: dict | None = None,
) -> WorkflowEntity:
    return WorkflowEntity(
        id=workflow_id,
        name=name,
        description=description,
        yaml=yaml,
        valid=valid,
        validation_error=validation_error,
        block_count=block_count,
        modified_at=modified_at,
        enabled=enabled,
        commit_sha=commit_sha,
        health_metrics=health_metrics
        or {
            "run_count": 2,
            "eval_health": 0.5,
            "eval_health_threshold": 0.75,
        },
    )


def _stub_workflow_service(workflows):
    mock_service = Mock()
    mock_service.list_workflows.return_value = workflows
    return mock_service


class TestWorkflowResponseModelShape:
    def test_workflow_response_model_includes_health_metadata_and_existing_fields(self):
        """WorkflowResponse must expose both legacy and health-related fields."""
        fields = WorkflowResponse.model_fields

        for field_name in (
            "id",
            "name",
            "description",
            "yaml",
            "canvas_state",
            "valid",
            "validation_error",
            "block_count",
            "modified_at",
            "enabled",
            "commit_sha",
        ):
            assert field_name in fields, f"Missing workflow response field: {field_name}"

        assert any(name in fields for name in ("health", "health_metrics")), (
            f"Expected a nested health field, got: {list(fields.keys())}"
        )


class TestWorkflowsListResponse:
    @pytest.mark.asyncio
    async def test_list_workflows_serializes_health_metadata_and_existing_fields(self):
        """GET /api/workflows should return the new health fields without losing old ones."""
        workflow = _make_workflow(
            workflow_id="wf_1",
            name="Research Flow",
            description="Research workflow",
            block_count=7,
            modified_at=1711900000.0,
            enabled=False,
            commit_sha="deadbeefcafebabe",
        )
        response = await list_workflows(service=_stub_workflow_service([workflow]))

        item = response.model_dump()["items"][0]
        assert item["id"] == "wf_1"
        assert item["name"] == "Research Flow"
        assert item["description"] == "Research workflow"
        assert item["yaml"] == "workflow:\n  name: Research Flow\n"
        assert item["valid"] is True
        assert item["validation_error"] is None
        assert item["block_count"] == 7
        assert item["modified_at"] == 1711900000.0
        assert item["enabled"] is False
        assert item["commit_sha"] == "deadbeefcafebabe"

        health = item.get("health") or item.get("health_metrics")
        assert health is not None, "Expected nested workflow health data in list response"
        assert health["run_count"] == 2
        assert health["eval_health"] == 0.5
        assert health["eval_health_threshold"] == 0.75

    @pytest.mark.asyncio
    async def test_list_workflows_keeps_backward_compatible_canvas_fields(self):
        """Legacy workflow fields must still be exposed alongside the new health data."""
        workflow = _make_workflow()
        workflow.canvas_state = {
            "nodes": [{"id": "node-1"}],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        }

        response = await list_workflows(service=_stub_workflow_service([workflow]))
        item = response.model_dump()["items"][0]

        assert "canvas_state" in item
        assert item["canvas_state"]["selected_node_id"] == "node-1"
        assert "yaml" in item
        assert "valid" in item
        assert "validation_error" in item


class TestWorkflowServiceDependencyWiring:
    def test_get_workflow_service_signature_includes_run_repo(self):
        """The dependency provider must wire a RunRepository into WorkflowService."""
        sig = inspect.signature(get_workflow_service)
        assert "run_repo" in sig.parameters, (
            f"get_workflow_service is missing run_repo wiring: {list(sig.parameters)}"
        )
