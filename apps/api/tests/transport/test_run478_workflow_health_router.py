"""Router-level tests for RUN-478: workflow health metrics on GET /api/workflows.

Uses the real app with dependency_overrides — no sys.modules stubbing.
"""

from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service
from runsight_api.transport.schemas import workflows as workflow_schemas

WorkflowResponse = workflow_schemas.WorkflowResponse

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


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
        kind="workflow",
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


class TestWorkflowResponseWarningsModelShape:
    def test_workflow_response_declares_warnings_as_a_list_field(self):
        fields = WorkflowResponse.model_fields

        assert "warnings" in fields
        assert fields["warnings"].default_factory is list

    def test_warning_item_declares_the_canonical_warning_payload_fields(self):
        warning_item = getattr(workflow_schemas, "WarningItem")
        fields = warning_item.model_fields

        assert set(fields) == {"message", "source", "context"}
        assert fields["message"].is_required()
        assert fields["source"].default is None
        assert fields["context"].default is None

    def test_warning_item_rejects_object_context_and_extra_fields(self):
        warning_item = getattr(workflow_schemas, "WarningItem")

        with pytest.raises(ValidationError):
            warning_item.model_validate(
                {
                    "message": "Tool definition warning",
                    "source": "tool_definitions",
                    "context": {"tool_id": "lookup_profile"},
                }
            )

        parsed = warning_item.model_validate(
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": None,
                "code": "W001",
                "severity": "warning",
            }
        )

        assert parsed.context is None
        assert not hasattr(parsed, "code")
        assert not hasattr(parsed, "severity")

    def test_workflow_response_parses_warning_items(self):
        response = WorkflowResponse.model_validate(
            {
                "id": "wf_1",
                "kind": "workflow",
                "warnings": [
                    {
                        "message": "Tool definition warning",
                        "source": "tool_definitions",
                        "context": "lookup_profile",
                    }
                ],
            }
        )

        assert len(response.warnings) == 1
        warning = response.warnings[0]
        assert warning.message == "Tool definition warning"
        assert warning.source == "tool_definitions"
        assert warning.context == "lookup_profile"

    def test_workflow_response_parses_null_context_warning_items(self):
        response = WorkflowResponse.model_validate(
            {
                "id": "wf_1",
                "kind": "workflow",
                "warnings": [
                    {
                        "message": "Tool definition warning",
                        "source": "tool_definitions",
                        "context": None,
                    }
                ],
            }
        )

        assert response.warnings[0].context is None


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
