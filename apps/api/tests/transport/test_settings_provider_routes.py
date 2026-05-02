"""Settings provider routes expose provider CRUD and connection-test contracts."""

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.routers.settings import ProviderCreate, ProviderUpdate
from runsight_api.transport.deps import (
    get_provider_service,
)
from tests.transport.settings_router_helpers import (
    _assert_provider_test_contract,
    _mock_provider,
)

client = TestClient(app)


def test_settings_providers_list():
    mock_service = Mock()
    mock_service.list_providers.return_value = [
        _mock_provider(
            provider_id="fixture-provider",
            name="Fixture Provider",
            models=["fixture-response-model", "fixture-chat-model"],
        ),
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
        provider_id="backup-provider",
        name="Backup Provider",
        models=["fixture-fallback-model"],
    )
    disabled_provider.is_active = False
    mock_service.list_providers.return_value = [disabled_provider]
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.get("/api/settings/providers")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["id"] == "backup-provider"
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
        provider_id="fixture-provider", name="Fixture Provider", models=[]
    )
    mock_service.create_provider.return_value = mock_provider
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    response = client.post(
        "/api/settings/providers",
        json={
            "id": "fixture-provider",
            "kind": "provider",
            "name": "Fixture Provider",
            "api_key_env": "dummy-xxx",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "fixture-provider"
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
    mock_provider = _mock_provider(
        provider_id="fixture-provider", name="Fixture Provider", models=[]
    )
    mock_service.create_provider.return_value = mock_provider
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/settings/providers",
            json={
                "id": "fixture-provider",
                "kind": "provider",
                "name": "Fixture Provider",
                "api_key_env": "dummy-xxx",
            },
        )
        assert response.status_code == 200
        mock_service.create_provider.assert_called_once_with(
            id="fixture-provider",
            kind="provider",
            name="Fixture Provider",
            api_key="dummy-xxx",
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
        provider_id="fixture-provider",
        name="Fixture Provider",
        models=[],
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/settings/providers",
            json={
                "name": "Fixture Provider",
                "api_key_env": "dummy-xxx",
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
        provider_id="fixture-provider",
        name="Fixture Provider",
        models=[],
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/providers/fixture-provider",
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
            "models": ["fixture-chat-model"],
        }
    )
    app.dependency_overrides[get_provider_service] = lambda: mock_service

    try:
        response = client.post("/api/settings/providers/fixture-provider/test")
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
                "provider_type": "fixture-provider",
                "api_key_env": "dummy-test",
                "base_url": "http://localhost/fixture-provider/v1",
            },
        )
        assert response.status_code == 200
        _assert_provider_test_contract(response.json())
    finally:
        app.dependency_overrides.clear()
