"""Generic base class for YAML-backed filesystem repositories."""

import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from urllib.parse import unquote

from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseYamlRepository(Generic[T]):
    """Base repository for YAML file-backed entities.

    Subclasses must set:
        entity_type: the Pydantic model class
        subdir: directory name under .runsight/
        not_found_error: exception class for missing entities
        entity_label: human-readable name for error messages
    """

    entity_type: Type[T]
    subdir: str
    not_found_error: Type[RunsightError]
    entity_label: str

    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.entity_dir = self.base_path / ".runsight" / self.subdir
        self.entity_dir.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, id: str) -> None:
        """Reject IDs that could escape the entity directory."""
        decoded = unquote(id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid id: {id!r}")

    def _get_path(self, id: str) -> Path:
        self._validate_id(id)
        return self.entity_dir / f"{id}.yaml"

    def list_all(self) -> List[T]:
        entities: List[T] = []
        for file in self.entity_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if "id" not in data:
                    data["id"] = file.stem
                entities.append(self.entity_type(**data))
            except Exception as e:
                logger.warning(f"Failed to load {self.entity_label.lower()} file {file}: {e}")
        return entities

    def get_by_id(self, id: str) -> Optional[T]:
        file_path = self._get_path(id)
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
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return self.entity_type(**data)

    def update(self, id: str, data: Dict[str, Any]) -> T:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise self.not_found_error(f"{self.entity_label} {id} not found")
        data["id"] = id
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return self.entity_type(**data)

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
