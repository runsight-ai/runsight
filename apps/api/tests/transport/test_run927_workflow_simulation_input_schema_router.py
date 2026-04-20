from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.logic.services.workflow_service import WorkflowService
from runsight_api.transport.deps import get_workflow_service


client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


def _service(*, git_service: Mock | None = None) -> WorkflowService:
    workflow_repo = Mock()
    run_repo = Mock()
    return WorkflowService(workflow_repo, run_repo, git_service=git_service or Mock())


def _dirty_workflow_yaml(*, input_type: str = "string") -> str:
    return f"""version: "1.0"
id: wf_927_dirty
kind: workflow
inputs:
  query:
    type: {input_type}
    description: Search query
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {{\"ok\": True}}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def _dirty_workflow_yaml_with_invalid_workflow_input_ref() -> str:
    return """version: "1.0"
id: wf_927_dirty
kind: workflow
inputs:
  query:
    type: string
blocks:
  start:
    type: code
    inputs:
      prompt:
        from: workflow.missing
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def _dirty_workflow_yaml_with_legacy_interface() -> str:
    return """version: "1.0"
id: wf_927_dirty
kind: workflow
interface:
  inputs:
    - name: query
      target: shared_memory.query
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


class TestWorkflowSimulationRouterInputSchema:
    def test_post_workflow_simulation_returns_prepared_input_schema_and_snapshot_identity(self):
        git_service = Mock()
        git_service.create_sim_branch.return_value = Mock(
            branch="sim/wf_927_dirty/20260419/abc12",
            sha="1234567890abcdef1234567890abcdef12345678",
        )
        service = _service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_927_dirty/simulations",
            json={"yaml": _dirty_workflow_yaml()},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["branch"] == "sim/wf_927_dirty/20260419/abc12"
        assert payload["commit_sha"] == "1234567890abcdef1234567890abcdef12345678"
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
            workflow_slug="wf_927_dirty",
            yaml_content=_dirty_workflow_yaml(),
            yaml_path="custom/workflows/wf_927_dirty.yaml",
        )

    def test_post_workflow_simulation_returns_empty_input_schema_when_no_inputs_are_declared(self):
        git_service = Mock()
        git_service.create_sim_branch.return_value = Mock(
            branch="sim/wf_927_dirty/20260419/abc12",
            sha="1234567890abcdef1234567890abcdef12345678",
        )
        service = _service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_927_dirty/simulations",
            json={
                "yaml": """version: "1.0"
id: wf_927_dirty
kind: workflow
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {\"ok\": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
""",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["branch"] == "sim/wf_927_dirty/20260419/abc12"
        assert payload["commit_sha"] == "1234567890abcdef1234567890abcdef12345678"
        assert payload["input_schema"] == {}

    def test_post_workflow_simulation_rejects_invalid_input_types_with_structured_backend_validation_errors(
        self,
    ):
        git_service = Mock()
        service = _service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_927_dirty/simulations",
            json={"yaml": _dirty_workflow_yaml(input_type="integer")},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_927_dirty"
        field = payload["details"]["fields"][0]
        assert field["field"] == "query"
        assert field["message"] == "Input 'query' is invalid."
        assert field["input_path"] == ["inputs", "query"]
        assert field["expected_type"] == "string"
        assert field["actual_type"] == "integer"
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_invalid_workflow_input_refs_with_structured_error(
        self,
    ):
        git_service = Mock()
        service = _service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_927_dirty/simulations",
            json={"yaml": _dirty_workflow_yaml_with_invalid_workflow_input_ref()},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_927_dirty"
        assert payload["details"]["fields"][0]["field"] == "__schema__"
        git_service.create_sim_branch.assert_not_called()

    def test_post_workflow_simulation_rejects_legacy_interface_yaml_with_structured_error(
        self,
    ):
        git_service = Mock()
        service = _service(git_service=git_service)
        app.dependency_overrides[get_workflow_service] = lambda: service

        response = client.post(
            "/api/workflows/wf_927_dirty/simulations",
            json={"yaml": _dirty_workflow_yaml_with_legacy_interface()},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
        assert payload["details"]["kind"] == "workflow_input_validation"
        assert payload["details"]["workflow_id"] == "wf_927_dirty"
        assert payload["details"]["fields"][0]["field"] == "__schema__"
        git_service.create_sim_branch.assert_not_called()
