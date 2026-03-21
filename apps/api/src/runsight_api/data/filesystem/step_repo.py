import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import unquote

from ...domain.value_objects import StepEntity
from ...domain.errors import StepNotFound

logger = logging.getLogger(__name__)


class StepRepository:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.steps_dir = self.base_path / ".runsight" / "steps"
        self.steps_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, id: str) -> Path:
        """Get the YAML file path for a step id, with path traversal validation."""
        decoded = unquote(id)
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise ValueError(f"Invalid path traversal in id: {id!r}")
        result = self.steps_dir / f"{id}.yaml"
        if not str(result.resolve()).startswith(str(self.steps_dir.resolve())):
            raise ValueError("Path traversal detected: resolved path escapes base directory")
        return result

    def list_all(self) -> List[StepEntity]:
        steps = []
        for file in self.steps_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if "id" not in data:
                    data["id"] = file.stem
                steps.append(StepEntity(**data))
            except Exception as e:
                logger.warning(f"Failed to load step file {file}: {e}")
        return steps

    def get_by_id(self, id: str) -> Optional[StepEntity]:
        file_path = self._get_path(id)
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "id" not in data:
            data["id"] = id
        return StepEntity(**data)

    def create(self, data: Dict[str, Any]) -> StepEntity:
        if "id" not in data:
            raise ValueError("Step must have an id")
        file_path = self._get_path(data["id"])
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return StepEntity(**data)

    def update(self, id: str, data: Dict[str, Any]) -> StepEntity:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise StepNotFound(f"Step {id} not found")
        data["id"] = id
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return StepEntity(**data)

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
