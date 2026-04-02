from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import AppSettingsConfig
from runsight_api.main import app
from runsight_api.transport.deps import (
    get_provider_service,
    get_settings_repo,
    get_settings_service,
)

client = TestClient(app)


def _mock_provider(*, provider_id: str, name: str, models: list[str]):
    provider = Mock()
    provider.id = provider_id
    provider.name = name
    provider.type = "custom"
    provider.status = "active"
    provider.api_key = "configured-key"
    provider.base_url = None
    provider.models = models
    provider.created_at = None
    provider.updated_at = None
    return provider


def _assert_provider_test_contract(payload: dict):
    assert payload["success"] in (True, False)
    assert isinstance(payload["message"], str)
    assert isinstance(payload["model_count"], int)
    assert payload["model_count"] >= 0
    assert payload["latency_ms"] >= 0


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


def test_settings_providers_list_keeps_disabled_provider_visible_for_management():
    mock_service = Mock()
    disabled_provider = _mock_provider(
        provider_id="anthropic",
        name="Anthropic",
        models=["claude-sonnet-4"],
    )
    disabled_provider.is_active = False
    mock_service.list_providers.return_value = [disabled_provider]
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.get("/api/settings/providers")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["id"] == "anthropic"
        assert payload["items"][0]["is_active"] is False
    finally:
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
    mock_service.test_connection = AsyncMock(
        return_value={
            "success": True,
            "message": "Connected — 1 models available",
            "models": ["gpt-4o"],
        }
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post("/api/settings/providers/openai/test")
        assert response.status_code == 200
        _assert_provider_test_contract(response.json())
    finally:
        app.dependency_overrides.clear()


def test_settings_providers_test_credentials_returns_setup_contract_shape():
    mock_service = Mock()
    mock_service.test_credentials = AsyncMock(
        return_value={
            "success": False,
            "message": "Connection failed (HTTP 401)",
            "models": [],
        }
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/settings/providers/test",
            json={
                "provider_type": "openai",
                "api_key_env": "sk-test",
                "base_url": "https://api.openai.com/v1",
            },
        )
        assert response.status_code == 200
        _assert_provider_test_contract(response.json())
    finally:
        app.dependency_overrides.clear()


def test_settings_models_list():
    import runsight_api.transport.deps as deps_module

    assert hasattr(deps_module, "get_settings_service"), (
        "deps.get_settings_service must exist so /api/settings/models can be wired "
        "to SettingsService"
    )

    mock_service = Mock()
    mock_service.get_model_defaults.return_value = [
        {
            "id": "openai",
            "provider_id": "openai",
            "provider_name": "OpenAI",
            "model_name": "gpt-4o",
            "is_default": True,
            "fallback_chain": ["gpt-4o-mini", "claude-3-5-sonnet"],
        }
    ]
    app.dependency_overrides[getattr(deps_module, "get_settings_service")] = lambda: mock_service

    try:
        response = client.get("/api/settings/models")
        assert response.status_code == 200
        assert response.json() == {
            "items": [
                {
                    "id": "openai",
                    "provider_id": "openai",
                    "provider_name": "OpenAI",
                    "model_name": "gpt-4o",
                    "is_default": True,
                    "fallback_chain": ["gpt-4o-mini", "claude-3-5-sonnet"],
                }
            ],
            "total": 1,
        }
        mock_service.get_model_defaults.assert_called_once_with()
    finally:
        app.dependency_overrides.clear()


def test_settings_models_put_updates_model_name():
    mock_service = Mock()
    mock_service.update_model_default.return_value = {
        "id": "openai",
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "model_name": "gpt-4.1",
        "is_default": True,
        "fallback_chain": ["gpt-4o-mini"],
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/models/openai",
            json={"model_name": "gpt-4.1", "is_default": True},
        )
        assert response.status_code == 200
        assert response.json() == {
            "id": "openai",
            "provider_id": "openai",
            "provider_name": "OpenAI",
            "model_name": "gpt-4.1",
            "is_default": True,
            "fallback_chain": ["gpt-4o-mini"],
        }
        mock_service.update_model_default.assert_called_once_with(
            provider_id="openai",
            model_name="gpt-4.1",
            is_default=True,
            fallback_chain=None,
        )
    finally:
        app.dependency_overrides.clear()


def test_settings_models_put_updates_fallback_chain():
    mock_service = Mock()
    mock_service.update_model_default.return_value = {
        "id": "openai",
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "model_name": "gpt-4.1",
        "is_default": True,
        "fallback_chain": ["gpt-4o-mini", "claude-3-5-sonnet"],
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/models/openai",
            json={"fallback_chain": ["gpt-4o-mini", "claude-3-5-sonnet"]},
        )
        assert response.status_code == 200
        assert response.json()["fallback_chain"] == ["gpt-4o-mini", "claude-3-5-sonnet"]
        mock_service.update_model_default.assert_called_once_with(
            provider_id="openai",
            model_name=None,
            is_default=None,
            fallback_chain=["gpt-4o-mini", "claude-3-5-sonnet"],
        )
    finally:
        app.dependency_overrides.clear()


def test_settings_models_put_404():
    from runsight_api.domain.errors import ProviderNotFound

    mock_service = Mock()
    mock_service.update_model_default.side_effect = ProviderNotFound("Provider missing not found")
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/models/missing",
            json={"model_name": "gpt-4.1"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_settings_budgets_list():
    app.dependency_overrides.clear()
    response = client.get("/api/settings/budgets")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_settings_app_get():
    try:
        repo = Mock(spec=FileSystemSettingsRepo)
        repo.get_settings.return_value = AppSettingsConfig(
            default_provider="openai",
            fallback_chain_enabled=False,
        )
        app.dependency_overrides[get_settings_repo] = lambda: repo
        response = client.get("/api/settings/app")
        assert response.status_code == 200
        assert response.json()["fallback_chain_enabled"] is False
    finally:
        app.dependency_overrides.clear()


def test_settings_app_put():
    try:
        repo = Mock(spec=FileSystemSettingsRepo)
        repo.update_settings.return_value = AppSettingsConfig(fallback_chain_enabled=False)
        app.dependency_overrides[get_settings_repo] = lambda: repo
        response = client.put("/api/settings/app", json={"fallback_chain_enabled": False})
        assert response.status_code == 200
        assert response.json()["fallback_chain_enabled"] is False
        repo.update_settings.assert_called_once_with({"fallback_chain_enabled": False})
    finally:
        app.dependency_overrides.clear()
