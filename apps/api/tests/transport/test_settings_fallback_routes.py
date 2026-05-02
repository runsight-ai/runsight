"""Settings fallback routes list and update provider fallback targets."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import (
    get_settings_service,
)

client = TestClient(app)


def test_settings_fallbacks_list():
    mock_service = Mock()
    mock_service.get_fallback_targets.return_value = [
        {
            "id": "fixture-provider",
            "provider_id": "fixture-provider",
            "provider_name": "Fixture Provider",
            "fallback_provider_id": "backup-provider",
            "fallback_model_id": "fixture-fallback-model",
        }
    ]
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.get("/api/settings/fallbacks")
        assert response.status_code == 200
        assert response.json() == {
            "items": [
                {
                    "id": "fixture-provider",
                    "provider_id": "fixture-provider",
                    "provider_name": "Fixture Provider",
                    "fallback_provider_id": "backup-provider",
                    "fallback_model_id": "fixture-fallback-model",
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
        "id": "fixture-provider",
        "provider_id": "fixture-provider",
        "provider_name": "Fixture Provider",
        "fallback_provider_id": "backup-provider",
        "fallback_model_id": "fixture-fallback-model",
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/fallbacks/fixture-provider",
            json={
                "fallback_provider_id": "backup-provider",
                "fallback_model_id": "fixture-fallback-model",
            },
        )
        assert response.status_code == 200
        assert response.json()["fallback_provider_id"] == "backup-provider"
        assert response.json()["fallback_model_id"] == "fixture-fallback-model"
        mock_service.update_fallback_target.assert_called_once_with(
            provider_id="fixture-provider",
            fallback_provider_id="backup-provider",
            fallback_model_id="fixture-fallback-model",
        )
    finally:
        app.dependency_overrides.clear()


def test_settings_fallbacks_put_allows_clearing_with_empty_strings():
    mock_service = Mock()
    mock_service.update_fallback_target.return_value = {
        "id": "fixture-provider",
        "provider_id": "fixture-provider",
        "provider_name": "Fixture Provider",
        "fallback_provider_id": None,
        "fallback_model_id": None,
    }
    app.dependency_overrides[get_settings_service] = lambda: mock_service

    try:
        response = client.put(
            "/api/settings/fallbacks/fixture-provider",
            json={"fallback_provider_id": "", "fallback_model_id": ""},
        )
        assert response.status_code == 200
        assert response.json()["fallback_provider_id"] is None
        assert response.json()["fallback_model_id"] is None
    finally:
        app.dependency_overrides.clear()
