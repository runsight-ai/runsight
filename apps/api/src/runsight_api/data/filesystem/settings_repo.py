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

# Flat setting keys that live at the top level of the YAML file
_FLAT_KEYS = {
    "auto_save",
    "onboarding_completed",
    "fallback_enabled",
}


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

        Returns None on missing file or parse failure.
        """
        if not self._settings_file.exists():
            return None
        try:
            with open(self._settings_file, "r") as f:
                data = yaml.safe_load(f)
            # yaml.safe_load returns None for empty files
            if data is None:
                return {}
            if not isinstance(data, dict):
                logger.warning("Settings file is not a YAML mapping: %s", self._settings_file)
                return None
            return data
        except Exception as e:
            logger.warning("Failed to read settings file %s: %s", self._settings_file, e)
            return None

    def _write_yaml(self, data: dict[str, Any]) -> None:
        """Write data to the settings YAML file atomically."""
        content = yaml.dump(data, sort_keys=False, default_flow_style=False)
        atomic_write(self._settings_file, content)

    def _load_yaml(self) -> dict[str, Any] | None:
        """Read settings YAML without rewriting legacy keys."""
        return self._read_yaml()

    # ------------------------------------------------------------------
    # Public API: flat settings
    # ------------------------------------------------------------------

    def get_settings(self) -> AppSettingsConfig:
        """Read flat app settings. Returns defaults if file is missing or invalid."""
        data = self._load_yaml()
        if data is None:
            return AppSettingsConfig()
        flat = {k: data.get(k) for k in _FLAT_KEYS if k in data}
        return AppSettingsConfig(**flat)

    def update_settings(self, updates: dict[str, Any]) -> AppSettingsConfig:
        """Merge partial updates into flat settings (shallow merge).

        Only keys in _FLAT_KEYS are considered. Other sections are preserved.
        """
        data = self._load_yaml() or {}
        for key in _FLAT_KEYS:
            if key in updates:
                data[key] = updates[key]
        self._write_yaml(data)
        flat = {k: data.get(k) for k in _FLAT_KEYS if k in data}
        return AppSettingsConfig(**flat)

    # ------------------------------------------------------------------
    # Public API: fallback map
    # ------------------------------------------------------------------

    def get_fallback_map(self) -> list[FallbackTargetEntry]:
        """Read the fallback map. Returns empty list if missing or invalid."""
        data = self._load_yaml()
        if data is None:
            return []
        fallback_map_data = data.get("fallback_map")
        if not isinstance(fallback_map_data, list):
            return []
        return [FallbackTargetEntry(**entry) for entry in fallback_map_data]

    def set_fallback_target(self, entry: FallbackTargetEntry) -> FallbackTargetEntry:
        """Upsert a fallback target by provider_id."""
        data = self._load_yaml() or {}
        fallback_map_data = data.get("fallback_map")
        if not isinstance(fallback_map_data, list):
            fallback_map_data = []

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
        fallback_map_data = data.get("fallback_map")
        if not isinstance(fallback_map_data, list):
            return False

        filtered = [entry for entry in fallback_map_data if entry.get("provider_id") != provider_id]
        if len(filtered) == len(fallback_map_data):
            return False

        data["fallback_map"] = filtered
        self._write_yaml(data)
        return True
