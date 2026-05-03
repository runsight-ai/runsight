"""Shared settings repository fixtures and builders."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo

PRIMARY_PROVIDER_ID = "primary-provider"
BACKUP_PROVIDER_ID = "backup-provider"
AUXILIARY_PROVIDER_ID = "auxiliary-provider"
PRIMARY_MODEL_ID = "primary-fixture-model"
BACKUP_MODEL_ID = "backup-fixture-model"
AUXILIARY_MODEL_ID = "auxiliary-fixture-model"


@pytest.fixture(name="repo")
def repo_fixture(tmp_path):
    return FileSystemSettingsRepo(base_path=str(tmp_path))


@pytest.fixture(name="settings_file")
def settings_file_fixture(tmp_path):
    return tmp_path / ".runsight" / "settings.yaml"


def settings_module():
    return importlib.import_module("runsight_api.domain.entities.settings")


def entities_module():
    return importlib.import_module("runsight_api.domain.entities")


def fallback_target_entry(**overrides):
    entry_cls = getattr(settings_module(), "FallbackTargetEntry")
    payload = {
        "provider_id": PRIMARY_PROVIDER_ID,
        "fallback_provider_id": BACKUP_PROVIDER_ID,
        "fallback_model_id": BACKUP_MODEL_ID,
    }
    payload.update(overrides)
    return entry_cls(**payload)


def fallback_map_entry(**overrides) -> dict:
    payload = {
        "provider_id": PRIMARY_PROVIDER_ID,
        "fallback_provider_id": BACKUP_PROVIDER_ID,
        "fallback_model_id": BACKUP_MODEL_ID,
    }
    payload.update(overrides)
    return payload


def write_settings_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
