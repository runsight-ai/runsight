from pathlib import Path
from unittest.mock import Mock

import yaml
from fastapi.testclient import TestClient

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.main import app
from runsight_api.transport import deps as deps_module
from runsight_api.transport.deps import get_git_service

client = TestClient(app)


def _write_provider(
    base_path: Path, *, provider_id: str, provider_type: str, is_active: bool
) -> None:
    provider_path = base_path / "custom" / "providers" / f"{provider_id}.yaml"
    provider_path.parent.mkdir(parents=True, exist_ok=True)
    provider_path.write_text(
        yaml.safe_dump(
            {
                "id": provider_id,
                "kind": "provider",
                "name": provider_id.capitalize(),
                "type": provider_type,
                "api_key": "${%s_API_KEY}" % provider_type.upper(),
                "status": "connected",
                "is_active": is_active,
                "models": ["claude-sonnet-4" if provider_type == "anthropic" else "gpt-4o"],
            },
            sort_keys=False,
        )
    )


def test_post_soul_rejects_disabled_provider_with_validation_error(tmp_path, monkeypatch):
    monkeypatch.setattr(deps_module.settings, "base_path", str(tmp_path))
    app.dependency_overrides[get_git_service] = lambda: Mock()
    _write_provider(tmp_path, provider_id="anthropic", provider_type="anthropic", is_active=False)

    try:
        response = client.post(
            "/api/souls",
            json={
                "id": "soul_disabled_provider",
                "kind": "soul",
                "name": "Analyst",
                "role": "Analyst",
                "system_prompt": "You analyze inputs.",
                "provider": "anthropic",
                "model_name": "claude-sonnet-4",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "disabled" in response.json()["error"].lower()


def test_put_soul_rejects_switching_to_disabled_provider_with_validation_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(deps_module.settings, "base_path", str(tmp_path))
    app.dependency_overrides[get_git_service] = lambda: Mock()
    _write_provider(tmp_path, provider_id="anthropic", provider_type="anthropic", is_active=False)
    SoulRepository(str(tmp_path)).create(
        {
            "id": "soul_existing",
            "kind": "soul",
            "name": "Existing Soul",
            "role": "Existing Soul",
            "system_prompt": "Keep working.",
            "provider": None,
            "model_name": None,
        }
    )

    try:
        response = client.put(
            "/api/souls/soul_existing",
            json={
                "provider": "anthropic",
                "model_name": "claude-sonnet-4",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "disabled" in response.json()["error"].lower()


def test_get_soul_keeps_existing_disabled_provider_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(deps_module.settings, "base_path", str(tmp_path))
    app.dependency_overrides[get_git_service] = lambda: Mock()
    _write_provider(tmp_path, provider_id="anthropic", provider_type="anthropic", is_active=False)
    SoulRepository(str(tmp_path)).create(
        {
            "id": "soul_disabled_existing",
            "kind": "soul",
            "name": "Existing Soul",
            "role": "Existing Soul",
            "system_prompt": "Keep working.",
            "provider": "anthropic",
            "model_name": "claude-sonnet-4",
        }
    )

    try:
        response = client.get("/api/souls/soul_disabled_existing")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["provider"] == "anthropic"
    assert response.json()["model_name"] == "claude-sonnet-4"
