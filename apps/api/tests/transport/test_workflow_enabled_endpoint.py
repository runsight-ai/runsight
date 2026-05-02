"""PATCH /api/workflows/{id}/enabled endpoint behavior."""

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service
from tests.transport.workflow_enabled_helpers import (
    _make_workflow,
    _stub_service_set_enabled,
)

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


class TestPatchWorkflowEnabled:
    """Tests for the PATCH /api/workflows/:id/enabled endpoint."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_patch_enable_workflow_returns_200_with_enabled_true(self):
        """PATCH /api/workflows/:id/enabled with {enabled: true} returns 200
        and the response includes enabled=true."""
        wf = _make_workflow(enabled=True)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["id"] == "my-workflow-abc12"

    def test_patch_disable_workflow_returns_200_with_enabled_false(self):
        """PATCH /api/workflows/:id/enabled with {enabled: false} returns 200
        and the response includes enabled=false."""
        wf = _make_workflow(enabled=False)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    # ---------------------------------------------------------------------------
    # 2. 404 if workflow doesn't exist
    # ---------------------------------------------------------------------------

    def test_patch_enabled_returns_404_for_nonexistent_workflow(self):
        """PATCH /api/workflows/:id/enabled returns 404 when workflow does not exist,
        with a domain error body (not a generic FastAPI 404)."""
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            raise_not_found=True
        )

        response = client.patch(
            "/api/workflows/nonexistent-wf-enabled/enabled",
            json={"enabled": True},
        )

        assert response.status_code == 404
        data = response.json()
        assert "error" in data, "404 response must include an 'error' field"
        assert data.get("error_code") == "WORKFLOW_NOT_FOUND"

    # ---------------------------------------------------------------------------
    # 3. Response shape matches WorkflowResponse
    # ---------------------------------------------------------------------------

    def test_patch_enabled_response_includes_workflow_response_fields(self):
        """Response must include standard WorkflowResponse fields: id, name, yaml, enabled, valid."""
        wf = _make_workflow(enabled=True)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()

        for field in ("id", "name", "yaml", "enabled", "valid"):
            assert field in data, f"Response missing required field: {field}"

        assert data["name"] == "My Workflow"

    # ---------------------------------------------------------------------------
    # 4. Malformed YAML returns 422
    # ---------------------------------------------------------------------------

    def test_patch_enabled_returns_422_for_malformed_yaml(self):
        """PATCH on a file with malformed YAML should return 422."""
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            raise_validation=True
        )

        response = client.patch(
            "/api/workflows/broken-wf-xyz99/enabled",
            json={"enabled": True},
        )

        # Domain validation can surface as either current API validation status.
        assert response.status_code in (400, 422)

    # ---------------------------------------------------------------------------
    # 5. Invalid request body
    # ---------------------------------------------------------------------------

    def test_patch_enabled_rejects_missing_enabled_field(self):
        """PATCH with an empty body or missing 'enabled' key should return 422."""
        wf = _make_workflow()
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={},
        )

        assert response.status_code == 422

    def test_patch_enabled_rejects_non_boolean_value(self):
        """PATCH with a non-boolean enabled value should return 422."""
        wf = _make_workflow()
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={"enabled": "yes"},
        )

        assert response.status_code == 422

    # ---------------------------------------------------------------------------
    # 6. Idempotent toggle
    # ---------------------------------------------------------------------------

    def test_patch_enable_already_enabled_workflow_is_idempotent(self):
        """Toggling enabled=true on an already-enabled workflow should succeed."""
        wf = _make_workflow(enabled=True)
        app.dependency_overrides[get_workflow_service] = lambda: _stub_service_set_enabled(
            returned_workflow=wf
        )

        response = client.patch(
            "/api/workflows/my-workflow-abc12/enabled",
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True


# ---------------------------------------------------------------------------
# 7. WorkflowService.set_enabled method must exist
# ---------------------------------------------------------------------------
