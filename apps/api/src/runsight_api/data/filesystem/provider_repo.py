"""Filesystem-backed provider repository.

Persists providers as YAML files in custom/providers/ with atomic writes.

ADR D3: The id field is NOT stored inside the YAML file — it is inferred
from the filename stem (e.g., openai.yaml -> id = "openai").
Provider ID = slugify(name) — provider names are unique by business rule.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import yaml

from ...domain.errors import ProviderNotFound
from ...domain.value_objects import ProviderEntity
from ._utils import atomic_write

logger = logging.getLogger(__name__)

# Fields that are API-only metadata, not part of the YAML file content
_META_FIELDS = {"id"}


class FileSystemProviderRepo:
    """Persists providers as YAML files in custom/providers/.

    Filename convention: {slugified_name}.yaml
    The provider id is the filename stem (ADR D3).
    """

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.providers_dir = self.base_path / "custom" / "providers"
        self.providers_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a provider name to a URL-safe slug.

        - Lowercase
        - Replace non-alphanumeric characters with hyphens
        - Collapse consecutive hyphens
        - Strip leading/trailing hyphens
        - Fall back to 'untitled' for empty input
        """
        if not name:
            return "untitled"
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug)
        slug = slug.strip("-")
        if not slug:
            return "untitled"
        return slug

    def _validate_id(self, provider_id: str) -> None:
        """Validate a provider ID against path traversal attacks."""
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
        """Build a ProviderEntity from YAML data.

        The id comes from the filename stem, not from inside the YAML.
        """
        entity_data = {k: v for k, v in data.items() if k not in _META_FIELDS}
        entity_data["id"] = stem
        return ProviderEntity(**entity_data)

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
            providers.append(self._build_entity(data, file.stem))
        return providers

    def get_by_id(self, provider_id: str) -> Optional[ProviderEntity]:
        """Retrieve a provider by its id (= filename stem)."""
        yaml_path = self._get_path(provider_id)
        if not yaml_path.exists():
            return None
        data = self._read_yaml(yaml_path)
        if data is None:
            return None
        return self._build_entity(data, provider_id)

    def get_by_type(self, provider_type: str) -> List[ProviderEntity]:
        """Retrieve all providers matching the given type."""
        return [p for p in self.list_all() if p.type == provider_type]

    def create(self, data: Dict[str, Any]) -> ProviderEntity:
        """Create a new provider file.

        The provider id is the slugified name. Raises ValueError if a
        provider with the same slug already exists.
        """
        name = data.get("name", "")
        slug = self._slugify(name)

        yaml_path = self.providers_dir / f"{slug}.yaml"
        if yaml_path.exists():
            raise ValueError(f"Provider with id '{slug}' already exists")

        # Build YAML data — exclude 'id' (ADR D3)
        yaml_data = {k: v for k, v in data.items() if k not in _META_FIELDS}
        entity = self._build_entity(yaml_data, slug)
        yaml_content = yaml.dump(yaml_data, sort_keys=False, default_flow_style=False)

        atomic_write(yaml_path, yaml_content)

        return entity

    def update(self, provider_id: str, data: Dict[str, Any]) -> ProviderEntity:
        """Update an existing provider file.

        Reads the existing file, merges with new data, and writes back atomically.
        Raises ProviderNotFound if the provider does not exist.
        """
        yaml_path = self._get_path(provider_id)
        if not yaml_path.exists():
            raise ProviderNotFound(f"Provider {provider_id} not found")

        existing = self._read_yaml(yaml_path) or {}
        self._build_entity(existing, provider_id)

        # Merge: new data overwrites existing fields (exclude meta fields)
        update_fields = {k: v for k, v in data.items() if k not in _META_FIELDS}
        merged = {**existing, **update_fields}
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
