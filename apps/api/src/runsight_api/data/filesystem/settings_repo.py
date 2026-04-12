"""Filesystem-backed settings repository.

Persists app settings as a single YAML file at .runsight/settings.yaml.
Manages flat app settings and per-provider fallback targets.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from ...domain.entities.settings import (
    AppSettingsConfig,
    FallbackTargetEntry,
)
from ._utils import atomic_write

logger = logging.getLogger(__name__)

# Flat app settings keys that live at the top level of the YAML file
_APP_SETTINGS_KEYS = {
    "onboarding_completed",
    "fallback_enabled",
}
_ALLOWED_TOP_LEVEL_KEYS = _APP_SETTINGS_KEYS | {"fallback_map"}


class FileSystemSettingsRepo:
    """Persists app settings in .runsight/settings.yaml.

    Flat settings and fallback_map coexist in a single YAML file.
    """

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self._settings_dir = self.base_path / ".runsight"
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._settings_file = self._settings_dir / "settings.yaml"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_yaml(self) -> dict[str, Any] | None:
        """Read and parse the settings YAML file.

        Returns None when file is missing.
        """
        if not self._settings_file.exists():
            return None
        try:
            with open(self._settings_file, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            message = f"Invalid settings YAML at {self._settings_file}: {e}"
            logger.warning(message)
            raise ValueError(message) from e
        except OSError as e:
            message = f"Failed to read settings file {self._settings_file}: {e}"
            logger.warning(message)
            raise ValueError(message) from e
        # yaml.safe_load returns None for empty files
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"Settings file must be a YAML mapping: {self._settings_file}")
        return data

    def _write_yaml(self, data: dict[str, Any]) -> None:
        """Write data to the settings YAML file atomically."""
        content = yaml.dump(data, sort_keys=False, default_flow_style=False)
        atomic_write(self._settings_file, content)

    def _validate_fallback_map(self, raw_fallback_map: Any) -> list[FallbackTargetEntry]:
        if raw_fallback_map is None:
            return []
        if not isinstance(raw_fallback_map, list):
            raise ValueError("fallback_map must be a list")

        entries: list[FallbackTargetEntry] = []
        for index, raw_entry in enumerate(raw_fallback_map):
            if not isinstance(raw_entry, dict):
                raise ValueError(f"fallback_map[{index}] must be an object")
            try:
                entries.append(FallbackTargetEntry(**raw_entry))
            except Exception as e:
                raise ValueError(f"Invalid fallback_map[{index}]: {e}") from e
        return entries

    def _validate_app_settings(self, data: dict[str, Any]) -> AppSettingsConfig:
        flat = {key: data.get(key) for key in _APP_SETTINGS_KEYS if key in data}
        try:
            return AppSettingsConfig(**flat)
        except Exception as e:
            raise ValueError(f"Invalid app settings values: {e}") from e

    def _load_yaml(self) -> dict[str, Any] | None:
        """Read and validate settings YAML against the current schema."""
        data = self._read_yaml()
        if data is None:
            return None

        unknown_keys = sorted(set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS)
        if unknown_keys:
            raise ValueError(f"Unsupported settings keys: {', '.join(unknown_keys)}")

        if "fallback_map" in data:
            self._validate_fallback_map(data["fallback_map"])
        self._validate_app_settings(data)

        return data

    # ------------------------------------------------------------------
    # Public API: flat settings
    # ------------------------------------------------------------------

    def get_settings(self) -> AppSettingsConfig:
        """Read flat app settings. Returns defaults when file is missing."""
        data = self._load_yaml()
        if data is None:
            return AppSettingsConfig()
        return self._validate_app_settings(data)

    def update_settings(self, updates: dict[str, Any]) -> AppSettingsConfig:
        """Merge partial updates into flat settings (shallow merge).

        Only keys in _APP_SETTINGS_KEYS are accepted. Other sections are preserved.
        """
        data = self._load_yaml() or {}
        unknown_update_keys = sorted(set(updates.keys()) - _APP_SETTINGS_KEYS)
        if unknown_update_keys:
            raise ValueError(f"Unsupported settings update keys: {', '.join(unknown_update_keys)}")

        for key in _APP_SETTINGS_KEYS:
            if key in updates:
                data[key] = updates[key]

        if "fallback_map" in data:
            self._validate_fallback_map(data["fallback_map"])

        settings_config = self._validate_app_settings(data)
        self._write_yaml(data)
        return settings_config

    # ------------------------------------------------------------------
    # Public API: fallback map
    # ------------------------------------------------------------------

    def get_fallback_map(self) -> list[FallbackTargetEntry]:
        """Read the fallback map. Returns empty list when the settings file is missing."""
        data = self._load_yaml()
        if data is None:
            return []
        return self._validate_fallback_map(data.get("fallback_map"))

    def set_fallback_target(self, entry: FallbackTargetEntry) -> FallbackTargetEntry:
        """Upsert a fallback target by provider_id."""
        data = self._load_yaml() or {}
        fallback_map_data = [
            existing.model_dump()
            for existing in self._validate_fallback_map(data.get("fallback_map"))
        ]

        entry_dict = entry.model_dump()
        updated = False
        for index, existing in enumerate(fallback_map_data):
            if existing.get("provider_id") == entry.provider_id:
                fallback_map_data[index] = entry_dict
                updated = True
                break

        if not updated:
            fallback_map_data.append(entry_dict)

        data["fallback_map"] = fallback_map_data
        self._write_yaml(data)
        return entry

    def remove_fallback_target(self, provider_id: str) -> bool:
        """Remove a fallback target by provider_id."""
        data = self._load_yaml() or {}
        fallback_map_data = self._validate_fallback_map(data.get("fallback_map"))

        filtered = [entry for entry in fallback_map_data if entry.provider_id != provider_id]
        if len(filtered) == len(fallback_map_data):
            return False

        data["fallback_map"] = [entry.model_dump() for entry in filtered]
        self._write_yaml(data)
        return True
