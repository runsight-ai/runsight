import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from ...domain.value_objects import TaskEntity
from ...domain.errors import TaskNotFound

logger = logging.getLogger(__name__)


class TaskRepository:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.tasks_dir = self.base_path / ".runsight" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, id: str) -> Path:
        return self.tasks_dir / f"{id}.yaml"

    def list_all(self) -> List[TaskEntity]:
        tasks = []
        for file in self.tasks_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if "id" not in data:
                    data["id"] = file.stem
                tasks.append(TaskEntity(**data))
            except Exception as e:
                logger.warning(f"Failed to load task file {file}: {e}")
        return tasks

    def get_by_id(self, id: str) -> Optional[TaskEntity]:
        file_path = self._get_path(id)
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "id" not in data:
            data["id"] = id
        return TaskEntity(**data)

    def create(self, data: Dict[str, Any]) -> TaskEntity:
        if "id" not in data:
            raise ValueError("Task must have an id")
        file_path = self._get_path(data["id"])
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return TaskEntity(**data)

    def update(self, id: str, data: Dict[str, Any]) -> TaskEntity:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise TaskNotFound(f"Task {id} not found")
        data["id"] = id
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return TaskEntity(**data)

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
