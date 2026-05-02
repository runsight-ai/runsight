from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service

from tests.transport.workflow_simulation_schema_helpers import (
    SIM_BRANCH,
    SIM_SHA,
    WORKFLOW_SLUG,
    WORKFLOW_YAML_PATH,
    dirty_workflow_yaml,
    dirty_workflow_yaml_with_invalid_workflow_input_ref,
    dirty_workflow_yaml_with_legacy_interface,
    dirty_workflow_yaml_with_sensitive_default,
    dirty_workflow_yaml_without_inputs,
    make_git_service_with_sim_branch,
    make_workflow_service,
)

client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


class TestWorkflowSimulationRouterInputSchema:
    def test_post_workflow_simulation_returns_prepared_input_schema_and_snapshot_identity(self):
        git_service = make_git_service_with_sim_branch()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml()},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["branch"] == SIM_BRANCH
        assert payload["commit_sha"] == SIM_SHA
        assert payload["input_schema"] == {
            "query": {
                "type": "string",
                "required": True,
                "default": None,
                "description": "Search query",
                "sensitive": False,
            }
        }
        git_service.create_sim_branch.assert_called_once_with(
            workflow_slug=WORKFLOW_SLUG,
            yaml_content=dirty_workflow_yaml(),
            yaml_path=WORKFLOW_YAML_PATH,
        )

    def test_post_workflow_simulation_returns_empty_input_schema_when_no_inputs_are_declared(self):
        git_service = make_git_service_with_sim_branch()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml_without_inputs()},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["branch"] == SIM_BRANCH
        assert payload["commit_sha"] == SIM_SHA
        assert payload["input_schema"] == {}

    def test_post_workflow_simulation_rejects_invalid_input_types_with_structured_backend_validation_errors(
        self,
    ):
        git_service = Mock()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml(input_type="integer")},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_dirty_simulation"
        field = payload["details"]["fields"][0]
        assert field["field"] == "query"
        assert field["message"] == "Input 'query' is invalid."
        assert field["input_path"] == ["inputs", "query"]
        assert field["expected_type"] == "string"
        assert field["actual_type"] == "integer"
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_sensitive_default_without_echoing_secret(
        self,
    ):
        git_service = Mock()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml_with_sensitive_default()},
        )

        assert response.status_code == 422
        assert "SECRET_LEAKED=True" not in response.text
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        field = payload["details"]["fields"][0]
        assert field["field"] == "api_key"
        assert field["actual_type"] is None
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_invalid_workflow_input_refs_with_structured_error(
        self,
    ):
        git_service = Mock()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml_with_invalid_workflow_input_ref()},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_dirty_simulation"
        assert payload["details"]["fields"][0]["field"] == "__schema__"
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_legacy_interface_yaml_with_structured_error(
        self,
    ):
        git_service = Mock()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={"yaml": dirty_workflow_yaml_with_legacy_interface()},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_dirty_simulation"
        assert payload["details"]["fields"][0]["field"] == "__schema__"
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_embedded_workflow_id_mismatch(self):
        git_service = Mock()
        service = make_workflow_service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_dirty_simulation/simulations",
            json={
                "yaml": dirty_workflow_yaml().replace(
                    "id: wf_dirty_simulation",
                    "id: other_workflow",
                )
            },
        )

        assert response.status_code == 400
        assert "embedded workflow id" in response.text
        git_service.create_sim_branch.assert_not_called()
