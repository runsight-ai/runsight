"""Red tests for RUN-822: provider identity must come from embedded YAML id."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo


def _provider_payload(**overrides):
    payload = {
        "kind": "provider",
        "name": "OpenAI",
        "type": "openai",
        "api_key": "${OPENAI_API_KEY}",
        "base_url": "https://api.openai.com/v1",
        "is_active": True,
        "status": "connected",
        "models": ["gpt-4o", "gpt-4o-mini"],
    }
    payload.update(overrides)
    return payload


def _write_provider_file(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_create_requires_explicit_embedded_id_and_uses_it_for_filename() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)
        providers_dir = Path(tmpdir) / "custom" / "providers"

        entity = repo.create(_provider_payload(id="openai-provider", name="OpenAI"))

        assert entity.id == "openai-provider"
        assert (providers_dir / "openai-provider.yaml").exists()
        assert not (providers_dir / "openai.yaml").exists()


def test_create_without_id_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)

        with pytest.raises(ValueError, match="id"):
            repo.create(_provider_payload())


def test_create_rejects_invalid_embedded_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)

        with pytest.raises(ValueError, match="provider id"):
            repo.create(_provider_payload(id="http"))


def test_list_all_does_not_infer_provider_id_from_filename_stem_when_yaml_id_differs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)
        providers_dir = Path(tmpdir) / "custom" / "providers"
        _write_provider_file(
            providers_dir / "legacy-provider.yaml",
            {
                "id": "provider-1",
                "kind": "provider",
                "name": "Legacy Provider",
                "type": "custom",
                "is_active": True,
                "status": "connected",
                "models": [],
            },
        )

        assert repo.list_all() == []


def test_get_by_id_does_not_return_provider_from_filename_stem_when_yaml_id_differs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)
        providers_dir = Path(tmpdir) / "custom" / "providers"
        _write_provider_file(
            providers_dir / "legacy-provider.yaml",
            {
                "id": "provider-1",
                "kind": "provider",
                "name": "Legacy Provider",
                "type": "custom",
                "is_active": True,
                "status": "connected",
                "models": [],
            },
        )

        assert repo.get_by_id("legacy-provider") is None


def test_update_does_not_accept_provider_filename_stem_when_yaml_id_differs() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = FileSystemProviderRepo(base_path=tmpdir)
        providers_dir = Path(tmpdir) / "custom" / "providers"
        _write_provider_file(
            providers_dir / "legacy-provider.yaml",
            {
                "id": "provider-1",
                "kind": "provider",
                "name": "Legacy Provider",
                "type": "custom",
                "is_active": True,
                "status": "connected",
                "models": [],
            },
        )

        with pytest.raises(ValueError, match="id"):
            repo.update("legacy-provider", {"status": "offline"})
