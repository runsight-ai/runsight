"""Generic base class for YAML-backed filesystem repositories."""

import logging
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from urllib.parse import unquote

import yaml
from pydantic import ValidationError

from runsight_core.identity import EntityKind, EntityRef

from ...domain.errors import RunsightError

logger = logging.getLogger(__name__)

T = TypeVar("T")
ENTITY_KIND_BY_LABEL = {
    "Soul": EntityKind.SOUL,
}


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
        # URL-decode first to catch encoded traversal sequences (e.g. %2e%2e%2f)
        decoded = unquote(id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {id!r}")

    def _get_path(self, id: str) -> Path:
        self._validate_id(id)
        return self.entity_dir / f"{id}.yaml"

    def _entity_ref(self, id: str) -> str:
        kind = ENTITY_KIND_BY_LABEL.get(self.entity_label)
        if kind is None:
            return id
        return str(EntityRef(kind, id))

    def _load_entity_data(self, file_path: Path) -> Dict[str, Any]:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{file_path.name}: YAML content is not a mapping")

        entity_id = data.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{file_path.name}: missing required id")
        if entity_id != file_path.stem:
            raise ValueError(
                f"{file_path.name}: embedded id {entity_id!r} does not match filename stem "
                f"{file_path.stem!r}"
            )
        return data

    def list_all(self) -> List[T]:
        entities: List[T] = []
        for file in self.entity_dir.glob("*.yaml"):
            try:
                data = self._load_entity_data(file)
                entities.append(self.entity_type(**data))
            except ValidationError:
                raise
            except Exception as e:
                logger.warning(f"Failed to load {self.entity_label.lower()} file {file}: {e}")
        return entities

    def get_by_id(self, id: str) -> Optional[T]:
        file_path = self._get_path(id)
        if not file_path.exists():
            return None
        try:
            data = self._load_entity_data(file_path)
            return self.entity_type(**data)
        except Exception as e:
            logger.warning(f"Failed to load {self.entity_label.lower()} file {file_path}: {e}")
            return None

    def create(self, data: Dict[str, Any]) -> T:
        entity_id = data.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{self.entity_label} must have an id")
        self._validate_id(entity_id)
        entity = self.entity_type(**data)
        file_path = self._get_path(entity_id)
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return entity

    def update(self, id: str, data: Dict[str, Any]) -> T:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise self.not_found_error(f"{self.entity_label} {self._entity_ref(id)} not found")
        entity_id = data.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{self.entity_label} must have an id")
        if entity_id != id:
            raise ValueError(
                f"{self.entity_label} id {self._entity_ref(entity_id)!r} "
                f"does not match requested id {self._entity_ref(id)!r}"
            )
        entity = self.entity_type(**data)
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return entity

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
