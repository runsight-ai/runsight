import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from ...domain.value_objects import WorkflowEntity
from ...domain.errors import WorkflowNotFound

logger = logging.getLogger(__name__)


class WorkflowRepository:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.workflows_dir = self.base_path / ".runsight" / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, id: str) -> Path:
        return self.workflows_dir / f"{id}.yaml"

    def list_all(self) -> List[WorkflowEntity]:
        workflows = []
        for file in self.workflows_dir.glob("*.yaml"):
            try:
                with open(file, "r") as f:
                    data = yaml.safe_load(f) or {}
                if "id" not in data:
                    data["id"] = file.stem
                workflows.append(WorkflowEntity(**data))
            except Exception as e:
                logger.warning(f"Failed to load workflow file {file}: {e}")
        return workflows

    def get_by_id(self, id: str) -> Optional[WorkflowEntity]:
        file_path = self._get_path(id)
        if not file_path.exists():
            return None
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "id" not in data:
            data["id"] = id
        return WorkflowEntity(**data)

    def create(self, data: Dict[str, Any]) -> WorkflowEntity:
        if "id" not in data:
            raise ValueError("Workflow must have an id")
        file_path = self._get_path(data["id"])
        with open(file_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return WorkflowEntity(**data)

    def update(self, id: str, data: Dict[str, Any]) -> WorkflowEntity:
        file_path = self._get_path(id)
        if not file_path.exists():
            raise WorkflowNotFound(f"Workflow {id} not found")

        with open(file_path, "r") as f:
            existing = yaml.safe_load(f) or {}

        # Merge partial updates to avoid dropping existing workflow fields.
        merged = {**existing, **data}
        merged["id"] = id
        with open(file_path, "w") as f:
            yaml.safe_dump(merged, f, sort_keys=False)
        return WorkflowEntity(**merged)

    def delete(self, id: str) -> bool:
        file_path = self._get_path(id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
