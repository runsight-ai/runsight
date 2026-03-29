from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_registry_service, get_step_repo

client = TestClient(app)


def test_steps_list():
    mock_registry = Mock()
    mock_registry.discover_steps.return_value = []
    mock_repo = Mock()
    mock_repo.list_all.return_value = []
    mock_repo._get_path.return_value = "/path/to/step"
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_step_repo] = lambda: mock_repo

    response = client.get("/api/steps")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


def test_steps_get_404():
    mock_registry = Mock()
    mock_registry.discover_steps.return_value = []
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = None
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_step_repo] = lambda: mock_repo

    response = client.get("/api/steps/nonexistent_step")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_steps_post():
    mock_registry = Mock()
    mock_repo = Mock()
    mock_entity = Mock()
    mock_entity.model_dump.return_value = {
        "id": "st_new",
        "name": "New Step",
        "type": "step",
        "path": "/path/to/st_new",
        "description": None,
    }
    mock_repo.create.return_value = mock_entity
    mock_repo._get_path.return_value = "/path/to/st_new"
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_step_repo] = lambda: mock_repo

    response = client.post("/api/steps", json={"name": "New Step", "type": "step"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "New Step"
    app.dependency_overrides.clear()


def test_steps_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/steps", json={"name": 123})  # name must be str
    assert response.status_code == 422


def test_steps_put_404():
    mock_registry = Mock()
    mock_registry.discover_steps.return_value = []
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = None
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_step_repo] = lambda: mock_repo

    response = client.put("/api/steps/missing", json={"name": "Updated"})
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_steps_delete():
    mock_registry = Mock()
    mock_repo = Mock()
    mock_repo.delete.return_value = True
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_step_repo] = lambda: mock_repo

    response = client.delete("/api/steps/st_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    app.dependency_overrides.clear()
