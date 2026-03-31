from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.errors import SoulInUse, SoulNotFound
from runsight_api.domain.value_objects import SoulEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_soul_service, get_workflow_repo

client = TestClient(app)


def test_souls_list():
    mock_service = Mock()
    mock_soul = SoulEntity(
        id="sl_1",
        role="Test Soul",
        system_prompt="Follow the prompt",
        model_name="gpt-4o-mini",
        workflow_count=2,
    )
    mock_service.list_souls.return_value = [mock_soul]
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.get("/api/souls")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "sl_1"
    assert data["items"][0]["role"] == "Test Soul"
    assert data["items"][0]["workflow_count"] == 2
    mock_service.list_souls.assert_called_once_with(query=None)
    app.dependency_overrides.clear()


def test_souls_get():
    mock_service = Mock()
    mock_soul = SoulEntity(
        id="sl_1",
        role="Test Soul",
        system_prompt="Follow the prompt",
        model_name="gpt-4o-mini",
    )
    mock_service.get_soul.return_value = mock_soul
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.get("/api/souls/sl_1")
    assert response.status_code == 200
    assert response.json()["id"] == "sl_1"
    assert response.json()["role"] == "Test Soul"
    assert response.json()["model_name"] == "gpt-4o-mini"
    app.dependency_overrides.clear()


def test_souls_get_404():
    mock_service = Mock()
    mock_service.get_soul.return_value = None
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.get("/api/souls/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_souls_post():
    mock_service = Mock()
    mock_soul = SoulEntity(
        id="sl_new",
        role="New Soul",
        system_prompt="Create the soul",
        model_name="gpt-4o",
    )
    mock_service.create_soul.return_value = mock_soul
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.post(
        "/api/souls",
        json={
            "id": "sl_new",
            "role": "New Soul",
            "system_prompt": "Create the soul",
            "model_name": "gpt-4o",
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == "sl_new"
    assert response.json()["role"] == "New Soul"
    assert response.json()["model_name"] == "gpt-4o"
    app.dependency_overrides.clear()


def test_souls_post_requires_role():
    mock_service = Mock()
    mock_service.create_soul.return_value = SoulEntity(id="unexpected", name="Unexpected")
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    response = client.post(
        "/api/souls",
        json={"id": "missing-role", "system_prompt": "Create the soul"},
    )
    assert response.status_code == 422
    mock_service.create_soul.assert_not_called()
    app.dependency_overrides.clear()


def test_souls_post_requires_system_prompt():
    mock_service = Mock()
    mock_service.create_soul.return_value = SoulEntity(id="unexpected", role="Unexpected")
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    response = client.post(
        "/api/souls",
        json={"id": "missing-system-prompt", "role": "New Soul"},
    )
    assert response.status_code == 422
    mock_service.create_soul.assert_not_called()
    app.dependency_overrides.clear()


def test_souls_put():
    mock_service = Mock()
    mock_soul = SoulEntity(
        id="sl_1",
        role="Updated Soul",
        system_prompt="Updated prompt",
        model_name="claude-sonnet",
    )
    mock_service.update_soul.return_value = mock_soul
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.put(
        "/api/souls/sl_1",
        json={
            "role": "Updated Soul",
            "system_prompt": "Updated prompt",
            "model_name": "claude-sonnet",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "Updated Soul"
    assert response.json()["model_name"] == "claude-sonnet"
    app.dependency_overrides.clear()


def test_souls_delete():
    mock_service = Mock()
    mock_workflow_repo = Mock()
    mock_service.delete_soul.return_value = True
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    app.dependency_overrides[get_workflow_repo] = lambda: mock_workflow_repo

    response = client.delete("/api/souls/sl_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    mock_service.delete_soul.assert_called_once_with(
        "sl_1",
        force=False,
        workflow_repo=mock_workflow_repo,
    )
    app.dependency_overrides.clear()


def test_souls_delete_force_true():
    mock_service = Mock()
    mock_workflow_repo = Mock()
    mock_service.delete_soul.return_value = True
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    app.dependency_overrides[get_workflow_repo] = lambda: mock_workflow_repo

    response = client.delete("/api/souls/sl_1?force=true")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    mock_service.delete_soul.assert_called_once_with(
        "sl_1",
        force=True,
        workflow_repo=mock_workflow_repo,
    )
    app.dependency_overrides.clear()


def test_souls_delete_in_use_returns_409():
    mock_service = Mock()
    mock_workflow_repo = Mock()
    mock_service.delete_soul.side_effect = SoulInUse(
        "Soul is referenced",
        details={"usages": [{"workflow_id": "wf-1", "workflow_name": "Review Flow"}]},
    )
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    app.dependency_overrides[get_workflow_repo] = lambda: mock_workflow_repo

    response = client.delete("/api/souls/sl_1")
    assert response.status_code == 409
    assert response.json()["error_code"] == "SOUL_IN_USE"
    assert response.json()["details"] == {
        "usages": [{"workflow_id": "wf-1", "workflow_name": "Review Flow"}]
    }
    app.dependency_overrides.clear()


def test_souls_delete_missing_returns_404():
    mock_service = Mock()
    mock_workflow_repo = Mock()
    mock_service.delete_soul.side_effect = SoulNotFound("Soul sl_1 not found")
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    app.dependency_overrides[get_workflow_repo] = lambda: mock_workflow_repo

    response = client.delete("/api/souls/sl_1")
    assert response.status_code == 404
    assert response.json()["error_code"] == "SOUL_NOT_FOUND"
    app.dependency_overrides.clear()


def test_souls_get_usages():
    mock_service = Mock()
    mock_service.get_soul_usages.return_value = [
        {"workflow_id": "wf-1", "workflow_name": "Research Flow"}
    ]
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.get("/api/souls/researcher/usages")
    assert response.status_code == 200
    assert response.json() == {
        "soul_id": "researcher",
        "usages": [{"workflow_id": "wf-1", "workflow_name": "Research Flow"}],
        "total": 1,
    }
    mock_service.get_soul_usages.assert_called_once_with("researcher")
    app.dependency_overrides.clear()


def test_souls_get_usages_missing_returns_404():
    mock_service = Mock()
    mock_workflow_repo = Mock()
    mock_service.get_soul_usages.side_effect = SoulNotFound("Soul missing not found")
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    app.dependency_overrides[get_workflow_repo] = lambda: mock_workflow_repo

    response = client.get("/api/souls/missing/usages")
    assert response.status_code == 404
    assert response.json()["error_code"] == "SOUL_NOT_FOUND"
    app.dependency_overrides.clear()
