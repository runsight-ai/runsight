# ruff: noqa: E402

import sys
import types
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub external dependencies that aren't available in the test environment.
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
    parser_pkg = types.ModuleType("runsight_core.yaml.parser")

    class _RunsightWorkflowFile:
        @classmethod
        def model_validate(cls, data):
            return data

    schema_pkg.RunsightWorkflowFile = _RunsightWorkflowFile
    parser_pkg.validate_tool_governance = lambda _: None
    yaml_pkg.schema = schema_pkg
    yaml_pkg.parser = parser_pkg
    runsight_core.yaml = yaml_pkg

    llm_pkg = types.ModuleType("runsight_core.llm")
    llm_pkg.__path__ = []
    model_catalog = types.ModuleType("runsight_core.llm.model_catalog")

    class _ModelCatalogPort:
        pass

    class _LiteLLMModelCatalog(_ModelCatalogPort):
        pass

    model_catalog.ModelCatalogPort = _ModelCatalogPort
    model_catalog.LiteLLMModelCatalog = _LiteLLMModelCatalog
    runsight_core.llm = llm_pkg

    sys.modules["runsight_core"] = runsight_core
    sys.modules["runsight_core.yaml"] = yaml_pkg
    sys.modules["runsight_core.yaml.schema"] = schema_pkg
    sys.modules["runsight_core.yaml.parser"] = parser_pkg
    sys.modules["runsight_core.llm"] = llm_pkg
    sys.modules["runsight_core.llm.model_catalog"] = model_catalog

if "ruamel" not in sys.modules:
    ruamel = types.ModuleType("ruamel")
    ruamel.__path__ = []
    ruamel_yaml = types.ModuleType("ruamel.yaml")

    class _YAML:
        def __init__(self, *args, **kwargs):
            self.preserve_quotes = False

        def load(self, _content):
            return {}

        def dump(self, _data, _stream):
            return None

    ruamel_yaml.YAML = _YAML
    ruamel.yaml = ruamel_yaml
    sys.modules["ruamel"] = ruamel
    sys.modules["ruamel.yaml"] = ruamel_yaml

fake_filesystem_pkg = types.ModuleType("runsight_api.data.filesystem")
fake_filesystem_pkg.__path__ = []
fake_workflow_repo = types.ModuleType("runsight_api.data.filesystem.workflow_repo")


class _WorkflowRepository:
    pass


fake_workflow_repo.WorkflowRepository = _WorkflowRepository
fake_filesystem_pkg.workflow_repo = fake_workflow_repo
sys.modules["runsight_api.data.filesystem"] = fake_filesystem_pkg
sys.modules["runsight_api.data.filesystem.workflow_repo"] = fake_workflow_repo

fake_repositories_pkg = types.ModuleType("runsight_api.data.repositories")
fake_repositories_pkg.__path__ = []
fake_run_repo = types.ModuleType("runsight_api.data.repositories.run_repo")


class _RunRepository:
    pass


fake_run_repo.RunRepository = _RunRepository
fake_repositories_pkg.run_repo = fake_run_repo
sys.modules["runsight_api.data.repositories"] = fake_repositories_pkg
sys.modules["runsight_api.data.repositories.run_repo"] = fake_run_repo

fake_eval_service = types.ModuleType("runsight_api.logic.services.eval_service")


class _EvalService:
    pass


fake_eval_service.EvalService = _EvalService
original_eval_service = sys.modules.get("runsight_api.logic.services.eval_service")
sys.modules["runsight_api.logic.services.eval_service"] = fake_eval_service

original_deps = sys.modules.get("runsight_api.transport.deps")
fake_deps = types.ModuleType("runsight_api.transport.deps")
fake_deps.get_workflow_service = lambda: None
fake_deps.get_eval_service = lambda: None
sys.modules["runsight_api.transport.deps"] = fake_deps

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.transport.deps import get_workflow_service
from runsight_api.transport.routers.workflows import router

if original_deps is not None:
    sys.modules["runsight_api.transport.deps"] = original_deps
else:
    del sys.modules["runsight_api.transport.deps"]

if original_eval_service is not None:
    sys.modules["runsight_api.logic.services.eval_service"] = original_eval_service
else:
    del sys.modules["runsight_api.logic.services.eval_service"]

app = FastAPI()
app.include_router(router, prefix="/api")
client = TestClient(app)


def test_workflows_list():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_1", name="Test Flow", blocks={}, edges=[])
    mock_service.list_workflows.return_value = [mock_wf]
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.get("/api/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "wf_1"
    app.dependency_overrides.clear()


def test_workflows_get():
    mock_service = Mock()
    mock_service.get_workflow.return_value = WorkflowEntity(
        id="wf_1",
        name="Test Flow",
        blocks={},
        edges=[],
    )
    mock_service.get_workflow_detail.return_value = WorkflowEntity(
        id="wf_1",
        name="Test Flow",
        blocks={},
        edges=[],
        commit_sha="abc123def456",
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    try:
        response = client.get("/api/workflows/wf_1")
        assert response.status_code == 200
        assert response.json()["id"] == "wf_1"
        assert response.json()["commit_sha"] == "abc123def456"
        mock_service.get_workflow_detail.assert_called_once_with("wf_1")
        mock_service.get_workflow.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_workflows_get_404():
    mock_service = Mock()
    mock_service.get_workflow.return_value = WorkflowEntity(
        id="wf_404",
        name="Existing Flow",
        blocks={},
        edges=[],
    )
    mock_service.get_workflow_detail.return_value = None
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    try:
        response = client.get("/api/workflows/missing")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_workflows_post():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_new", name="New Workflow", blocks={}, edges=[])
    mock_service.create_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows",
        json={"name": "New Workflow", "yaml": "workflow:\n  name: New Workflow\n"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "wf_new"
    app.dependency_overrides.clear()


def test_workflows_post_requires_yaml():
    mock_service = Mock()
    mock_service.create_workflow.return_value = WorkflowEntity(
        id="wf_new",
        name="New Workflow",
        blocks={},
        edges=[],
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post("/api/workflows", json={"name": "New Workflow"})

    assert response.status_code == 422
    mock_service.create_workflow.assert_not_called()
    app.dependency_overrides.clear()


def test_workflows_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/workflows", json={"name": 123})  # name must be str
    assert response.status_code == 422


def test_workflows_put():
    mock_service = Mock()
    mock_wf = WorkflowEntity(id="wf_1", name="Updated Flow", blocks={}, edges=[])
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        "/api/workflows/wf_1",
        json={"name": "Updated Flow", "yaml": "workflow:\n  name: Updated Flow\n"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Flow"
    app.dependency_overrides.clear()


def test_workflows_put_requires_yaml():
    mock_service = Mock()
    mock_service.update_workflow.return_value = WorkflowEntity(
        id="wf_1",
        name="Updated Flow",
        blocks={},
        edges=[],
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put("/api/workflows/wf_1", json={"name": "Updated Flow"})

    assert response.status_code == 422
    mock_service.update_workflow.assert_not_called()
    app.dependency_overrides.clear()


def test_workflows_put_with_canvas_state():
    mock_service = Mock()
    canvas_state = {
        "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
        "edges": [],
        "viewport": {"x": 1, "y": 2, "zoom": 0.75},
        "selected_node_id": "node-1",
        "canvas_mode": "dag",
    }
    mock_wf = WorkflowEntity(
        id="wf_1",
        name="Updated Flow",
        blocks={},
        edges=[],
        canvas_state=canvas_state,
    )
    mock_service.update_workflow.return_value = mock_wf
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        "/api/workflows/wf_1",
        json={
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": canvas_state,
        },
    )
    assert response.status_code == 200
    assert response.json()["canvas_state"]["selected_node_id"] == "node-1"
    mock_service.update_workflow.assert_called_once()
    _, called_data = mock_service.update_workflow.call_args.args
    assert "canvas_state" in called_data
    assert called_data["canvas_state"]["viewport"]["zoom"] == 0.75
    app.dependency_overrides.clear()


def test_workflows_put_with_invalid_canvas_mode_422():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.put(
        "/api/workflows/wf_1",
        json={
            "canvas_state": {
                "nodes": [],
                "edges": [],
                "viewport": {"x": 0, "y": 0, "zoom": 1},
                "selected_node_id": None,
                "canvas_mode": "hsm",
            }
        },
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


def test_workflows_post_commit_returns_commit_metadata():
    mock_service = Mock()
    mock_service.commit_workflow.return_value = {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    draft = {
        "yaml": "workflow:\n  name: Updated Flow\n",
        "canvas_state": {
            "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
            "edges": [],
            "viewport": {"x": 1, "y": 2, "zoom": 0.75},
            "selected_node_id": "node-1",
            "canvas_mode": "dag",
        },
        "message": "Save workflow to main",
    }

    response = client.post("/api/workflows/wf_1/commits", json=draft)

    assert response.status_code == 200
    assert response.json() == {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    mock_service.commit_workflow.assert_called_once_with(
        "wf_1",
        {
            "yaml": "workflow:\n  name: Updated Flow\n",
            "canvas_state": {
                "nodes": [{"id": "node-1", "position": {"x": 10, "y": 20}}],
                "edges": [],
                "viewport": {"x": 1, "y": 2, "zoom": 0.75},
                "selected_node_id": "node-1",
                "canvas_mode": "dag",
            },
        },
        "Save workflow to main",
    )
    app.dependency_overrides.clear()


def test_workflows_post_commit_requires_commit_message():
    mock_service = Mock()
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/wf_1/commits",
        json={"yaml": "workflow:\n  name: Updated Flow\n"},
    )

    assert response.status_code == 422
    mock_service.commit_workflow.assert_not_called()
    app.dependency_overrides.clear()


def test_workflows_post_commit_requires_yaml():
    mock_service = Mock()
    mock_service.commit_workflow.return_value = {
        "hash": "abc123def456",
        "message": "Save workflow to main",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/wf_1/commits",
        json={"message": "Save workflow to main"},
    )

    assert response.status_code == 422
    mock_service.commit_workflow.assert_not_called()
    app.dependency_overrides.clear()


def test_workflows_delete():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = {
        "id": "wf_1",
        "deleted": True,
        "runs_deleted": 2,
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete("/api/workflows/wf_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["runs_deleted"] == 2
    mock_service.delete_workflow.assert_called_once_with("wf_1", force=False)
    app.dependency_overrides.clear()


def test_workflows_delete_force_true_forwards_and_returns_runs_deleted():
    mock_service = Mock()
    mock_service.delete_workflow.return_value = {
        "id": "wf_1",
        "deleted": True,
        "runs_deleted": 4,
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete("/api/workflows/wf_1?force=true")
    assert response.status_code == 200
    assert response.json() == {"id": "wf_1", "deleted": True, "runs_deleted": 4}
    mock_service.delete_workflow.assert_called_once_with("wf_1", force=True)
    app.dependency_overrides.clear()


def test_workflows_delete_active_runs_returns_409():
    from runsight_api.domain.errors import WorkflowHasActiveRuns

    mock_service = Mock()
    mock_service.delete_workflow.side_effect = WorkflowHasActiveRuns(
        "Workflow wf_1 has active runs"
    )
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.delete("/api/workflows/wf_1")
    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKFLOW_HAS_ACTIVE_RUNS"
    app.dependency_overrides.clear()


def test_workflows_post_simulations_returns_branch_and_commit_sha():
    mock_service = Mock()
    posted_yaml = "workflow:\n  name: Sim Snapshot\n  steps:\n    - id: latest-step\n"
    mock_service.create_simulation.return_value = {
        "branch": "sim/wf_123/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
    }
    app.dependency_overrides[get_workflow_service] = lambda: mock_service

    response = client.post(
        "/api/workflows/wf_123/simulations",
        json={"yaml": posted_yaml},
    )

    assert response.status_code == 200
    assert response.json() == {
        "branch": "sim/wf_123/20260330/abc12",
        "commit_sha": "1234567890abcdef1234567890abcdef12345678",
    }
    mock_service.create_simulation.assert_called_once()
    args, kwargs = mock_service.create_simulation.call_args
    forwarded_workflow_id = kwargs.get("workflow_id")
    if forwarded_workflow_id is None:
        forwarded_workflow_id = next((arg for arg in args if arg == "wf_123"), None)
    forwarded_yaml = kwargs.get("yaml")
    if forwarded_yaml is None:
        forwarded_yaml = next((arg for arg in args if arg == posted_yaml), None)
    assert forwarded_workflow_id == "wf_123"
    assert forwarded_yaml == posted_yaml
    app.dependency_overrides.clear()
