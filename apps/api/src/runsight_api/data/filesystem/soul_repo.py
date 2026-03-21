import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import unquote

from ...domain.value_objects import SoulEntity
from ...domain.errors import SoulNotFound

logger = logging.getLogger(__name__)


class SoulRepository:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.souls_dir = self.base_path / ".runsight" / "souls"
        self.souls_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, id: str) -> Path:
        """Get the YAML file path for a soul id, with path traversal validation."""
        decoded = unquote(id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {id!r}")
        result = self.souls_dir / f"{id}.yaml"
        if not str(result.resolve()).startswith(str(self.souls_dir.resolve())):
            raise ValueError("Path traversal detected: resolved path escapes base directory")
        return result

    def list_all(self) -> List[SoulEntity]:
        souls = []
        for file in self.souls_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if "id" not in data:
                    data["id"] = file.stem
                souls.append(SoulEntity(**data))
            except Exception as e:
                logger.warning(f"Failed to load soul file {file}: {e}")
        return souls

    def get_by_id(self, id: str) -> Optional[SoulEntity]:
        file_path = self._get_path(id)
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "id" not in data:
            data["id"] = id
        return SoulEntity(**data)

    def create(self, data: Dict[str, Any]) -> SoulEntity:
        if "id" not in data:
            raise ValueError("Soul must have an id")
        file_path = self._get_path(data["id"])
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return SoulEntity(**data)

    def update(self, id: str, data: Dict[str, Any]) -> SoulEntity:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise SoulNotFound(f"Soul {id} not found")
        data["id"] = id
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return SoulEntity(**data)

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
