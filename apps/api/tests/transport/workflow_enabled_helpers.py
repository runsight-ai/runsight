"""Shared workflow enabled endpoint helpers."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.main import app

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_workflow(
    workflow_id: str = "my-workflow-abc12",
    *,
    name: str = "My Workflow",
    yaml: str = "workflow:\n  name: My Workflow\nenabled: true\n",
    valid: bool = True,
    enabled: bool = True,
) -> WorkflowEntity:
    return WorkflowEntity(
        kind="workflow",
        id=workflow_id,
        name=name,
        yaml=yaml,
        valid=valid,
        enabled=enabled,
    )


def _stub_service_set_enabled(
    *,
    returned_workflow: WorkflowEntity | None = None,
    raise_not_found: bool = False,
    raise_validation: bool = False,
):
    """Build a mock WorkflowService that supports set_enabled."""
    mock_service = Mock()

    if raise_not_found:
        from runsight_api.domain.errors import WorkflowNotFound

        mock_service.set_enabled.side_effect = WorkflowNotFound("Workflow not found")
    elif raise_validation:
        from runsight_api.domain.errors import InputValidationError

        mock_service.set_enabled.side_effect = InputValidationError("Malformed YAML")
    elif returned_workflow is not None:
        mock_service.set_enabled.return_value = returned_workflow
    return mock_service


# ---------------------------------------------------------------------------
# 1. PATCH /api/workflows/:id/enabled -- happy path: enable
# ---------------------------------------------------------------------------
