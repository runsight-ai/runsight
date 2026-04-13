"""Generic base class for YAML-backed filesystem repositories."""

import logging
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from urllib.parse import unquote

import yaml
from pydantic import ValidationError

from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseYamlRepository(Generic[T]):
    """Base repository for YAML file-backed entities.

    Subclasses must set:
        entity_type: the Pydantic model class
        subdir: directory name under root_dir/
        root_dir: storage root under base_path
        not_found_error: exception class for missing entities
        entity_label: human-readable name for error messages
    """

    entity_type: Type[T]
    subdir: str
    root_dir: str = ".runsight"
    not_found_error: Type[RunsightError]
    entity_label: str

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.entity_dir = self.base_path / self.root_dir / self.subdir
        self.entity_dir.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, id: str) -> None:
        """Reject IDs that could escape the entity directory."""
        decoded = unquote(id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid id: {id!r}")

    def _get_path(self, id: str) -> Path:
        self._validate_id(id)
        return self.entity_dir / f"{id}.yaml"

    def _resolve_existing_path(self, id: str) -> Path:
        """Resolve an entity path by filename first, then by embedded YAML id.

        Some hand-authored assets may have a filename that does not match the
        entity id stored inside the YAML. We still want detail/update/delete
        operations to work against those files.
        """
        direct_path = self._get_path(id)
        if direct_path.exists():
            return direct_path

        for file_path in self.entity_dir.glob("*.yaml"):
            try:
                with open(file_path, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                continue

            if data.get("id") == id:
                return file_path

        return direct_path

    def list_all(self) -> List[T]:
        entities: List[T] = []
        for file in self.entity_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.warning(f"Failed to load {self.entity_label.lower()} file {file}: {e}")
                continue

            try:
                if "id" not in data:
                    data["id"] = file.stem
                entities.append(self.entity_type(**data))
            except ValidationError:
                raise
            except Exception as e:
                logger.warning(f"Failed to load {self.entity_label.lower()} file {file}: {e}")
        return entities

    def get_by_id(self, id: str) -> Optional[T]:
        file_path = self._resolve_existing_path(id)
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "id" not in data:
            data["id"] = id
        return self.entity_type(**data)

    def create(self, data: Dict[str, Any]) -> T:
        if "id" not in data:
            raise ValueError(f"{self.entity_label} must have an id")
        self._validate_id(data["id"])
        file_path = self.entity_dir / f"{data['id']}.yaml"
        entity = self.entity_type(**data)
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return entity

    def update(self, id: str, data: Dict[str, Any]) -> T:
        file_path = self._resolve_existing_path(id)
        if not file_path.exists():
            raise self.not_found_error(f"{self.entity_label} {id} not found")
        data["id"] = id
        entity = self.entity_type(**data)
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return entity

    def delete(self, id: str) -> bool:
        file_path = self._resolve_existing_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
