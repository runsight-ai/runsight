"""App settings routes expose the current fallback-enabled settings shape."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.domain.entities.settings import AppSettingsConfig
from runsight_api.main import app
from runsight_api.transport.deps import (
    get_settings_repo,
)

client = TestClient(app)


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
            json={"default_provider": "fixture-provider"},
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
