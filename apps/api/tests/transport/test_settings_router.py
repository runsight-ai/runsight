from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_provider_service, get_session

client = TestClient(app)


def _mock_provider(*, provider_id: str, name: str, models: list[str]):
    provider = Mock()
    provider.id = provider_id
    provider.name = name
    provider.status = "active"
    provider.api_key = "configured-key"
    provider.base_url = None
    provider.models = models
    provider.created_at = None
    provider.updated_at = None
    return provider


def test_settings_providers_list():
    mock_service = Mock()
    mock_service.list_providers.return_value = [
        _mock_provider(
            provider_id="openai",
            name="OpenAI",
            models=["gpt-4.1", "gpt-4o"],
        ),
        _mock_provider(
            provider_id="empty-provider",
            name="Empty Provider",
            models=[],
        ),
    ]
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.get("/api/settings/providers")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert data["items"][0]["model_count"] == 2
    assert data["items"][1]["model_count"] == 0
    app.dependency_overrides.clear()


def test_settings_providers_get_404():
    mock_service = Mock()
    mock_service.get_provider.return_value = None
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.get("/api/settings/providers/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_settings_providers_post():
    mock_service = Mock()
    mock_provider = _mock_provider(
        provider_id="openai",
        name="OpenAI",
        models=[],
    )
    mock_service.create_provider.return_value = mock_provider
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.post(
        "/api/settings/providers",
        json={"name": "OpenAI", "api_key_env": "sk-xxx"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "openai"
    assert data["model_count"] == 0
    app.dependency_overrides.clear()


def test_settings_providers_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/settings/providers", json={})  # name required
    assert response.status_code == 422


def test_settings_providers_put_404():
    mock_service = Mock()
    mock_service.update_provider.return_value = None
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.put(
        "/api/settings/providers/missing",
        json={"name": "Updated"},
    )
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_settings_providers_delete_404():
    mock_service = Mock()
    mock_service.delete_provider.return_value = False
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.delete("/api/settings/providers/missing")
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_settings_providers_test():
    mock_service = Mock()
    mock_service.test_connection = AsyncMock(return_value={"success": True})
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.post("/api/settings/providers/openai/test")
    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_settings_models_list():
    app.dependency_overrides.clear()
    response = client.get("/api/settings/models")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_settings_budgets_list():
    app.dependency_overrides.clear()
    response = client.get("/api/settings/budgets")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_settings_app_get():
    import tempfile

    from sqlmodel import Session, SQLModel, create_engine

    # File-based DB so all connections share schema (unlike :memory:)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    try:

        def _get_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = _get_session
        response = client.get("/api/settings/app")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        import os

        os.unlink(db_path)


def test_settings_app_put():
    import os
    import tempfile

    from sqlmodel import Session, SQLModel, create_engine

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    try:

        def _get_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = _get_session
        response = client.put("/api/settings/app", json={"theme": "dark"})
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        os.unlink(db_path)
