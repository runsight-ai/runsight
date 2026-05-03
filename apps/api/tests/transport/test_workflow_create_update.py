from __future__ import annotations

from textwrap import dedent
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.logic.services.workflow_service import WorkflowService
from runsight_api.main import app
from runsight_api.transport.deps import get_workflow_service

client = TestClient(app, raise_server_exceptions=False)


def _workflow_yaml(*, workflow_id: str = "research-review", name: str = "Research Review") -> str:
    return (
        dedent(
            f"""
            version: "1.0"
            id: {workflow_id}
            kind: workflow
            workflow:
              name: {name}
              entry: start
              transitions: []
            blocks: {{}}
            """
        ).strip()
        + "\n"
    )


def _override_real_workflow_service(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    service = WorkflowService(repo, Mock())
    app.dependency_overrides[get_workflow_service] = lambda: service


def test_workflows_post_rejects_duplicate_embedded_workflow_id(tmp_path) -> None:
    _override_real_workflow_service(tmp_path)
    workflow_path = tmp_path / "custom" / "workflows" / "research-review.yaml"
    first_yaml = _workflow_yaml(name="Research Review")
    second_yaml = _workflow_yaml(name="Research Review v2")

    try:
        response = client.post("/api/workflows", json={"yaml": first_yaml})
        assert response.status_code == 200
        assert response.json()["id"] == "research-review"
        assert workflow_path.exists()
        original_contents = workflow_path.read_text(encoding="utf-8")

        duplicate = client.post("/api/workflows", json={"yaml": second_yaml})

        assert duplicate.status_code in {400, 409, 422}
        assert workflow_path.read_text(encoding="utf-8") == original_contents
    finally:
        app.dependency_overrides.clear()


def test_workflows_put_rejects_embedded_workflow_id_mismatch(tmp_path) -> None:
    _override_real_workflow_service(tmp_path)
    workflow_path = tmp_path / "custom" / "workflows" / "research-review.yaml"
    good_yaml = _workflow_yaml(name="Research Review")
    bad_yaml = _workflow_yaml(workflow_id="changed-id", name="Research Review")

    try:
        response = client.post("/api/workflows", json={"yaml": good_yaml})
        assert response.status_code == 200
        assert workflow_path.exists()
        original_contents = workflow_path.read_text(encoding="utf-8")

        mismatch = client.put("/api/workflows/research-review", json={"yaml": bad_yaml})

        assert mismatch.status_code in {400, 409, 422}
        assert workflow_path.read_text(encoding="utf-8") == original_contents
    finally:
        app.dependency_overrides.clear()
