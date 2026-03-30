from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import SoulEntity
from runsight_api.main import app
from runsight_api.transport.deps import get_soul_service

client = TestClient(app)


def test_souls_list():
    mock_service = Mock()
    mock_soul = SoulEntity(
        id="sl_1",
        role="Test Soul",
        system_prompt="Follow the prompt",
        model_name="gpt-4o-mini",
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
    assert data["items"][0]["workflow_count"] == 0
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


def test_souls_post_requires_role_and_system_prompt():
    mock_service = Mock()
    mock_service.create_soul.return_value = SoulEntity(id="unexpected", name="Unexpected")
    app.dependency_overrides[get_soul_service] = lambda: mock_service
    response = client.post("/api/souls", json={"id": "missing-fields"})
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
    mock_service.delete_soul.return_value = True
    app.dependency_overrides[get_soul_service] = lambda: mock_service

    response = client.delete("/api/souls/sl_1")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    app.dependency_overrides.clear()
