"""Red tests for RUN-478: workflow health metrics on GET /api/workflows."""
# ruff: noqa: E402

import sys
import types
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
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

original_deps = sys.modules.get("runsight_api.transport.deps")
fake_deps = types.ModuleType("runsight_api.transport.deps")
fake_deps.get_workflow_service = lambda: None
sys.modules["runsight_api.transport.deps"] = fake_deps

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.transport.deps import get_workflow_service
from runsight_api.transport.routers.workflows import router
from runsight_api.transport.schemas.workflows import WorkflowResponse

if original_deps is not None:
    sys.modules["runsight_api.transport.deps"] = original_deps
else:
    del sys.modules["runsight_api.transport.deps"]

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


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
    health: dict | None = None,
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
        health=health
        if health is not None
        else {
            "eval_health": "success",
            "run_count": 2,
            "eval_pass_pct": 95.0,
            "total_cost_usd": 0.30,
            "regression_count": 1,
        },
    )


def _stub_workflow_service(workflows):
    mock_service = Mock()
    mock_service.list_workflows.return_value = workflows
    return mock_service


def _workflow_health_model_fields():
    health_annotation = WorkflowResponse.model_fields["health"].annotation
    health_model_fields = getattr(health_annotation, "model_fields", None)
    if health_model_fields is not None:
        return health_model_fields

    for candidate in getattr(health_annotation, "__args__", ()):
        health_model_fields = getattr(candidate, "model_fields", None)
        if health_model_fields is not None:
            return health_model_fields

    raise AssertionError("WorkflowResponse.health must be a structured model")


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
            "health",
        ):
            assert field_name in fields, f"Missing workflow response field: {field_name}"

        assert "eval_health" in _workflow_health_model_fields()


class TestWorkflowsListResponse:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_list_workflows_serializes_health_metadata_and_existing_fields(self):
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
        app.dependency_overrides[get_workflow_service] = lambda: _stub_workflow_service([workflow])

        response = client.get("/api/workflows")
        assert response.status_code == 200

        item = response.json()["items"][0]
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

        health = item.get("health")
        assert health is not None, "Expected nested workflow health data in list response"
        assert health["eval_health"] is not None
        assert health["run_count"] == 2
        assert health["eval_pass_pct"] == 95.0
        assert health["total_cost_usd"] == 0.30
        assert health["regression_count"] == 1

    @pytest.mark.parametrize(
        ("health", "expected_run_count"),
        [
            (
                {
                    "eval_health": None,
                    "run_count": 0,
                    "eval_pass_pct": None,
                    "total_cost_usd": 0.0,
                    "regression_count": 0,
                },
                0,
            ),
            (
                {
                    "eval_health": None,
                    "run_count": 1,
                    "eval_pass_pct": None,
                    "total_cost_usd": 0.25,
                    "regression_count": 0,
                },
                1,
            ),
        ],
    )
    def test_list_workflows_serializes_null_eval_health_for_empty_and_no_eval_cases(
        self,
        health,
        expected_run_count,
    ):
        """GET /api/workflows should serialize null eval fields for empty and no-eval workflows."""
        workflow = _make_workflow(health=health)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_workflow_service([workflow])

        response = client.get("/api/workflows")
        assert response.status_code == 200

        item = response.json()["items"][0]
        health = item.get("health")
        assert health is not None, "Expected nested workflow health data in list response"
        assert health["run_count"] == expected_run_count
        assert health["eval_health"] is None
        assert health["eval_pass_pct"] is None

    def test_list_workflows_keeps_canvas_fields_alongside_health_payload(self):
        """Canvas fields should still serialize when the health payload is added."""
        workflow = _make_workflow()
        workflow.canvas_state = {
            "nodes": [{"id": "node-1"}],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        }
        app.dependency_overrides[get_workflow_service] = lambda: _stub_workflow_service([workflow])

        response = client.get("/api/workflows")
        assert response.status_code == 200

        item = response.json()["items"][0]
        assert "canvas_state" in item
        assert item["canvas_state"]["selected_node_id"] == "node-1"
        assert item["block_count"] == 7
        assert item["health"]["eval_health"] is not None
