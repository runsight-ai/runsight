"""Filesystem-backed settings repository.

Persists app settings as a single YAML file at .runsight/settings.yaml.
Manages default provider, auto_save, onboarding state, fallback chains,
and model defaults.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ...domain.entities.settings import (
    AppSettingsConfig,
    FallbackChainEntry,
    ModelDefaultEntry,
)
from ._utils import atomic_write

logger = logging.getLogger(__name__)

# Flat setting keys that live at the top level of the YAML file
_FLAT_KEYS = {"default_provider", "auto_save", "onboarding_completed"}


class FileSystemSettingsRepo:
    """Persists app settings in .runsight/settings.yaml.

    All sections (flat settings, fallback_chain, model_defaults) coexist
    in a single YAML file.
    """

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self._settings_dir = self.base_path / ".runsight"
        self._settings_dir.mkdir(parents=True, exist_ok=True)
        self._settings_file = self._settings_dir / "settings.yaml"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_yaml(self) -> Optional[Dict[str, Any]]:
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

    def _write_yaml(self, data: Dict[str, Any]) -> None:
        """Write data to the settings YAML file atomically."""
        content = yaml.dump(data, sort_keys=False, default_flow_style=False)
        atomic_write(self._settings_file, content)

    # ------------------------------------------------------------------
    # Public API: flat settings
    # ------------------------------------------------------------------

    def get_settings(self) -> AppSettingsConfig:
        """Read flat app settings. Returns defaults if file is missing or invalid."""
        data = self._read_yaml()
        if data is None:
            return AppSettingsConfig()
        flat = {k: data.get(k) for k in _FLAT_KEYS if k in data}
        return AppSettingsConfig(**flat)

    def update_settings(self, updates: Dict[str, Any]) -> AppSettingsConfig:
        """Merge partial updates into flat settings (shallow merge).

        Only keys in _FLAT_KEYS are considered. Other sections (fallback_chain,
        model_defaults) are preserved.
        """
        data = self._read_yaml() or {}
        for key in _FLAT_KEYS:
            if key in updates:
                data[key] = updates[key]
        self._write_yaml(data)
        flat = {k: data.get(k) for k in _FLAT_KEYS if k in data}
        return AppSettingsConfig(**flat)

    # ------------------------------------------------------------------
    # Public API: fallback chain
    # ------------------------------------------------------------------

    def get_fallback_chain(self) -> List[FallbackChainEntry]:
        """Read the fallback chain. Returns empty list if missing or invalid."""
        data = self._read_yaml()
        if data is None:
            return []
        chain_data = data.get("fallback_chain")
        if not isinstance(chain_data, list):
            return []
        return [FallbackChainEntry(**entry) for entry in chain_data]

    def update_fallback_chain(self, chain: List[FallbackChainEntry]) -> List[FallbackChainEntry]:
        """Replace the entire fallback chain (full replacement, not merge)."""
        data = self._read_yaml() or {}
        data["fallback_chain"] = [entry.model_dump() for entry in chain]
        self._write_yaml(data)
        return chain

    # ------------------------------------------------------------------
    # Public API: model defaults
    # ------------------------------------------------------------------

    def list_model_defaults(self) -> List[ModelDefaultEntry]:
        """List all model default entries. Returns empty list if missing or invalid."""
        data = self._read_yaml()
        if data is None:
            return []
        defaults_data = data.get("model_defaults")
        if not isinstance(defaults_data, list):
            return []
        return [ModelDefaultEntry(**entry) for entry in defaults_data]

    def set_model_default(self, entry: ModelDefaultEntry) -> ModelDefaultEntry:
        """Upsert a model default by (provider_id, model_id) composite key."""
        data = self._read_yaml() or {}
        defaults_data: List[Dict[str, Any]] = data.get("model_defaults", [])
        if not isinstance(defaults_data, list):
            defaults_data = []

        # Find existing entry by composite key
        entry_dict = entry.model_dump()
        updated = False
        for i, existing in enumerate(defaults_data):
            if (
                existing.get("provider_id") == entry.provider_id
                and existing.get("model_id") == entry.model_id
            ):
                defaults_data[i] = entry_dict
                updated = True
                break

        if not updated:
            defaults_data.append(entry_dict)

        data["model_defaults"] = defaults_data
        self._write_yaml(data)
        return entry
