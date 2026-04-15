from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import AppSettingsConfig
from runsight_api.main import app
from runsight_api.transport.routers.settings import ProviderCreate, ProviderUpdate
from runsight_api.transport.deps import (
    get_provider_service,
    get_settings_repo,
    get_settings_service,
)

client = TestClient(app)


def _mock_provider(*, provider_id: str, name: str, models: list[str]):
    provider = Mock()
    provider.id = provider_id
    provider.kind = "provider"
    provider.name = name
    provider.type = "custom"
    provider.status = "active"
    provider.api_key = "configured-key"
    provider.base_url = None
    provider.models = models
    provider.created_at = None
    provider.updated_at = None
    provider.is_active = True
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
        _mock_provider(provider_id="openai", name="OpenAI", models=["gpt-4.1", "gpt-4o"]),
        _mock_provider(provider_id="empty-provider", name="Empty Provider", models=[]),
    ]
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.get("/api/settings/providers")
    assert response.status_code == 200
    data = response.json()
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
    mock_provider = _mock_provider(provider_id="openai", name="OpenAI", models=[])
    mock_service.create_provider.return_value = mock_provider
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.post(
        "/api/settings/providers",
        json={"id": "openai", "kind": "provider", "name": "OpenAI", "api_key_env": "sk-xxx"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "openai"
    assert data["model_count"] == 0
    app.dependency_overrides.clear()


def test_settings_provider_create_request_requires_embedded_identity_fields():
    assert ProviderCreate.model_fields["id"].is_required()
    assert ProviderCreate.model_fields["kind"].is_required()


def test_settings_provider_update_request_requires_embedded_identity_fields():
    assert ProviderUpdate.model_fields["id"].is_required()
    assert ProviderUpdate.model_fields["kind"].is_required()


def test_settings_providers_post_passes_embedded_identity_to_service():
    mock_service = Mock()
    mock_provider = _mock_provider(provider_id="openai", name="OpenAI", models=[])
    mock_service.create_provider.return_value = mock_provider
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/settings/providers",
            json={
                "id": "openai",
                "kind": "provider",
                "name": "OpenAI",
                "api_key_env": "sk-xxx",
            },
        )
        assert response.status_code == 200
        mock_service.create_provider.assert_called_once_with(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="sk-xxx",
            base_url=None,
        )
    finally:
        app.dependency_overrides.clear()


def test_settings_providers_post_422():
    app.dependency_overrides.clear()
    response = client.post("/api/settings/providers", json={})
    assert response.status_code == 422


def test_settings_providers_post_rejects_unknown_fields():
    mock_service = Mock()
    mock_service.create_provider.return_value = _mock_provider(
        provider_id="openai",
        name="OpenAI",
        models=[],
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/settings/providers",
            json={
                "name": "OpenAI",
                "api_key_env": "sk-xxx",
                "custom_notes": "unsupported",
            },
        )
        assert response.status_code == 422
        mock_service.create_provider.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_settings_providers_put_404():
    mock_service = Mock()
    mock_service.update_provider.return_value = None
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.put(
        "/api/settings/providers/missing",
        json={"id": "missing", "kind": "provider", "name": "Updated"},
    )
    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_settings_providers_put_rejects_unknown_fields():
    mock_service = Mock()
    mock_service.update_provider.return_value = _mock_provider(
        provider_id="openai",
        name="OpenAI",
        models=[],
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/providers/openai",
            json={"name": "Updated", "custom_notes": "unsupported"},
        )
        assert response.status_code == 422
        mock_service.update_provider.assert_not_called()
    finally:
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
            "message": "Connected - 1 models available",
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


def test_settings_fallbacks_list():
    mock_service = Mock()
    mock_service.get_fallback_targets.return_value = [
        {
            "id": "openai",
            "provider_id": "openai",
            "provider_name": "OpenAI",
            "fallback_provider_id": "anthropic",
            "fallback_model_id": "claude-sonnet-4",
        }
    ]
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.get("/api/settings/fallbacks")
        assert response.status_code == 200
        assert response.json() == {
            "items": [
                {
                    "id": "openai",
                    "provider_id": "openai",
                    "provider_name": "OpenAI",
                    "fallback_provider_id": "anthropic",
                    "fallback_model_id": "claude-sonnet-4",
                }
            ],
            "total": 1,
        }
        mock_service.get_fallback_targets.assert_called_once_with()
    finally:
        app.dependency_overrides.clear()


def test_settings_fallbacks_put_updates_fallback_pair():
    mock_service = Mock()
    mock_service.update_fallback_target.return_value = {
        "id": "openai",
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "fallback_provider_id": "anthropic",
        "fallback_model_id": "claude-sonnet-4",
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/fallbacks/openai",
            json={
                "fallback_provider_id": "anthropic",
                "fallback_model_id": "claude-sonnet-4",
            },
        )
        assert response.status_code == 200
        assert response.json()["fallback_provider_id"] == "anthropic"
        assert response.json()["fallback_model_id"] == "claude-sonnet-4"
        mock_service.update_fallback_target.assert_called_once_with(
            provider_id="openai",
            fallback_provider_id="anthropic",
            fallback_model_id="claude-sonnet-4",
        )
    finally:
        app.dependency_overrides.clear()


def test_settings_fallbacks_put_allows_clearing_with_empty_strings():
    mock_service = Mock()
    mock_service.update_fallback_target.return_value = {
        "id": "openai",
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "fallback_provider_id": None,
        "fallback_model_id": None,
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/fallbacks/openai",
            json={"fallback_provider_id": "", "fallback_model_id": ""},
        )
        assert response.status_code == 200
        assert response.json()["fallback_provider_id"] is None
        assert response.json()["fallback_model_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_app_settings_get_omits_auto_save_and_keeps_fallback_enabled():
    mock_repo = Mock(spec=FileSystemSettingsRepo)
    mock_repo.get_settings.return_value = AppSettingsConfig(
        onboarding_completed=True,
        fallback_enabled=False,
    )
    app.dependency_overrides[get_settings_repo] = lambda: mock_repo

    try:
        response = client.get("/api/settings/app")
        assert response.status_code == 200
        assert "auto_save" not in response.json()
        assert response.json()["fallback_enabled"] is False
        assert "default_provider" not in response.json()
    finally:
        app.dependency_overrides.clear()


def test_app_settings_put_keeps_fallback_settings_without_auto_save():
    mock_repo = Mock(spec=FileSystemSettingsRepo)
    mock_repo.update_settings.return_value = AppSettingsConfig(
        onboarding_completed=True,
        fallback_enabled=False,
    )
    app.dependency_overrides[get_settings_repo] = lambda: mock_repo

    try:
        response = client.put(
            "/api/settings/app",
            json={"onboarding_completed": True, "fallback_enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["fallback_enabled"] is False
        assert "auto_save" not in response.json()
        assert "default_provider" not in response.json()
        mock_repo.update_settings.assert_called_once_with(
            {"onboarding_completed": True, "fallback_enabled": False}
        )
    finally:
        app.dependency_overrides.clear()


def test_app_settings_put_rejects_unsupported_fields():
    mock_repo = Mock(spec=FileSystemSettingsRepo)
    mock_repo.update_settings.return_value = AppSettingsConfig(
        onboarding_completed=True,
        fallback_enabled=False,
    )
    app.dependency_overrides[get_settings_repo] = lambda: mock_repo

    try:
        response = client.put(
            "/api/settings/app",
            json={"default_provider": "openai"},
        )
        assert response.status_code == 422
        mock_repo.update_settings.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "payload",
    [
        {"onboarding_completed": "yes"},
        {"fallback_enabled": 1},
        {"onboarding_completed": None},
        {"fallback_enabled": None},
    ],
)
def test_app_settings_put_rejects_non_boolean_values(payload):
    mock_repo = Mock(spec=FileSystemSettingsRepo)
    mock_repo.update_settings.return_value = AppSettingsConfig(
        onboarding_completed=False,
        fallback_enabled=False,
    )
    app.dependency_overrides[get_settings_repo] = lambda: mock_repo

    try:
        response = client.put("/api/settings/app", json=payload)
        assert response.status_code == 422
        mock_repo.update_settings.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_settings_openapi_exposes_fallback_routes_and_current_app_settings_shape():
    spec = app.openapi()

    assert "/api/settings/fallbacks" in spec["paths"]
    assert "/api/settings/fallbacks/{provider_id}" in spec["paths"]
    assert "/api/settings/models" not in spec["paths"]
    assert "/api/settings/models/{model_id}" not in spec["paths"]

    app_settings_props = spec["components"]["schemas"]["AppSettingsOut"]["properties"]
    assert "fallback_enabled" in app_settings_props
    assert "onboarding_completed" in app_settings_props
    assert "auto_save" not in app_settings_props
    assert "default_provider" not in app_settings_props
    assert "fallback_chain_enabled" not in app_settings_props

    app_settings_update_props = spec["components"]["schemas"]["AppSettingsUpdate"]["properties"]
    assert app_settings_update_props["onboarding_completed"] == {
        "type": "boolean",
        "title": "Onboarding Completed",
    }
    assert app_settings_update_props["fallback_enabled"] == {
        "type": "boolean",
        "title": "Fallback Enabled",
    }
