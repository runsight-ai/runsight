"""Filesystem-backed provider repository.

Persists providers as YAML files in custom/providers/ with atomic writes.

The provider id is embedded in the YAML file and must match the filename
stem exactly.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pydantic import ValidationError
from runsight_core.identity import EntityKind, EntityRef

from ...domain.errors import ProviderNotFound
from ...domain.value_objects import ProviderEntity
from ._utils import atomic_write

logger = logging.getLogger(__name__)


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


class FileSystemProviderRepo:
    """Persists providers as YAML files in custom/providers/.

    Filename convention: {provider_id}.yaml
    """

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.providers_dir = self.base_path / "custom" / "providers"
        self.providers_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_id(self, provider_id: str) -> None:
        """Validate a provider ID against path traversal attacks."""
        from urllib.parse import unquote

        decoded = unquote(provider_id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {provider_id!r}")
        result = self.providers_dir / f"{provider_id}.yaml"
        if not str(result.resolve()).startswith(str(self.providers_dir.resolve())):
            raise ValueError("Path traversal detected: resolved path escapes base directory")

    def _get_path(self, provider_id: str) -> Path:
        """Get the YAML file path for a provider id, with path traversal validation."""
        self._validate_id(provider_id)
        return self.providers_dir / f"{provider_id}.yaml"

    def _read_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Read and parse a YAML file. Returns None on failure."""
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to read provider file %s: %s", path, e)
            return None

    def _build_entity(self, data: Dict[str, Any], stem: str) -> ProviderEntity:
        """Build a ProviderEntity from YAML data and validate its identity."""
        entity_id = data.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{stem}.yaml: missing required id")
        if entity_id != stem:
            raise ValueError(
                f"{stem}.yaml: embedded id {entity_id!r} does not match filename stem {stem!r}"
            )

        entity_data = dict(data)
        return ProviderEntity(**entity_data)

    def _validate_entity_data(self, data: Dict[str, Any], stem: str) -> None:
        """Validate provider YAML before merging update fields."""
        self._build_entity(data, stem)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_all(self) -> List[ProviderEntity]:
        """List all providers found in custom/providers/*.yaml.

        Skips malformed YAML files with a logged warning.
        """
        providers: List[ProviderEntity] = []
        for file in sorted(self.providers_dir.glob("*.yaml")):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.warning("Failed to load provider file %s: %s", file, e)
                continue
            try:
                providers.append(self._build_entity(data, file.stem))
            except ValidationError:
                raise
            except Exception as e:
                logger.warning("Failed to load provider file %s: %s", file, e)
        return providers

    def get_by_id(self, provider_id: str) -> Optional[ProviderEntity]:
        """Retrieve a provider by its id (= filename stem)."""
        yaml_path = self._get_path(provider_id)
        if not yaml_path.exists():
            return None
        data = self._read_yaml(yaml_path)
        if data is None:
            return None
        try:
            return self._build_entity(data, provider_id)
        except Exception as e:
            logger.warning("Failed to load provider file %s: %s", yaml_path, e)
            return None

    def get_by_type(self, provider_type: str) -> List[ProviderEntity]:
        """Retrieve all providers matching the given type."""
        return [p for p in self.list_all() if p.type == provider_type]

    def create(self, data: Dict[str, Any]) -> ProviderEntity:
        """Create a new provider file.

        The provider id must be embedded in the YAML payload.
        Raises ValueError if a provider with the same id already exists.
        """
        provider_id = data.get("id")
        if not isinstance(provider_id, str) or not provider_id:
            raise ValueError("Provider must have an id")
        self._validate_id(provider_id)

        yaml_path = self._get_path(provider_id)
        if yaml_path.exists():
            raise ValueError(
                f"Provider {_provider_ref(provider_id)} already exists. "
                "Use update() to modify an existing provider."
            )

        yaml_data = dict(data)
        yaml_content = yaml.dump(yaml_data, sort_keys=False, default_flow_style=False)
        entity = self._build_entity(yaml_data, provider_id)

        atomic_write(yaml_path, yaml_content)

        return entity

    def update(self, provider_id: str, data: Dict[str, Any]) -> ProviderEntity:
        """Update an existing provider file.

        Reads the existing file, validates the embedded id, merges with new data,
        and writes back atomically.
        Raises ProviderNotFound if the provider does not exist.
        """
        yaml_path = self._get_path(provider_id)
        if not yaml_path.exists():
            raise ProviderNotFound(f"Provider {_provider_ref(provider_id)} not found")

        existing = self._read_yaml(yaml_path) or {}
        self._build_entity(existing, provider_id)

        update_id = data.get("id")
        if not isinstance(update_id, str) or not update_id:
            raise ValueError("Provider must have an id")
        if update_id != provider_id:
            raise ValueError(
                f"Provider id {_provider_ref(update_id)!r} "
                f"does not match requested id {_provider_ref(provider_id)!r}"
            )

        merged = {**existing, **{k: v for k, v in data.items() if k != "id"}}
        merged["id"] = provider_id
        entity = self._build_entity(merged, provider_id)

        yaml_content = yaml.dump(merged, sort_keys=False, default_flow_style=False)
        atomic_write(yaml_path, yaml_content)

        return entity

    def delete(self, provider_id: str) -> bool:
        """Delete a provider YAML file.

        Returns True if the file was deleted, False if it did not exist.
        """
        yaml_path = self._get_path(provider_id)
        if yaml_path.exists():
            yaml_path.unlink()
            return True
        return False
