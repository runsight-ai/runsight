from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_registry_service, get_task_repo

client = TestClient(app)


def test_tasks_list():
    mock_registry = Mock()
    mock_registry.discover_tasks.return_value = []
    mock_repo = Mock()
    mock_repo.list_all.return_value = []
    mock_repo._get_path.return_value = "/path/to/task"
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_task_repo] = lambda: mock_repo

    response = client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


def test_tasks_get_404():
    mock_registry = Mock()
    mock_registry.discover_tasks.return_value = []
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = None
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_task_repo] = lambda: mock_repo

    response = client.get("/api/tasks/nonexistent_task")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_tasks_post():
    mock_registry = Mock()
    mock_repo = Mock()
    mock_entity = Mock()
    mock_entity.model_dump.return_value = {
        "id": "tk_new",
        "name": "New Task",
        "type": "task",
        "path": "/path/to/tk_new",
        "description": None,
    }
    mock_repo.create.return_value = mock_entity
    mock_repo._get_path.return_value = "/path/to/tk_new"
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_task_repo] = lambda: mock_repo

    response = client.post("/api/tasks", json={"name": "New Task", "type": "task"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "New Task"
    app.dependency_overrides.clear()


def test_tasks_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/tasks", json={"name": 123})  # name must be str
    assert response.status_code == 422


def test_tasks_put_404():
    mock_registry = Mock()
    mock_registry.discover_tasks.return_value = []
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = None
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_task_repo] = lambda: mock_repo

    response = client.put("/api/tasks/missing", json={"name": "Updated"})
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_tasks_delete():
    mock_registry = Mock()
    mock_repo = Mock()
    mock_repo.delete.return_value = True
    app.dependency_overrides[get_registry_service] = lambda: mock_registry
    app.dependency_overrides[get_task_repo] = lambda: mock_repo

    response = client.delete("/api/tasks/tk_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    app.dependency_overrides.clear()
