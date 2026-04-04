from pathlib import Path
from typing import Any, Dict, List


class RegistryService:
    def __init__(self, custom_dir: str = "custom"):
        self.custom_dir = Path(custom_dir)

    def discover_steps(self) -> List[Dict[str, Any]]:
        steps = []
        steps_dir = self.custom_dir / "steps"
        if not steps_dir.exists():
            return steps

        for file in steps_dir.glob("**/*.py"):
            if file.name == "__init__.py" or file.name.startswith("."):
                continue

            steps.append(
                {
                    "id": file.stem,
                    "path": str(file),
                    "type": "step",
                    "name": file.stem.replace("_", " ").title(),
                }
            )

        return steps

    def discover_tasks(self) -> List[Dict[str, Any]]:
        tasks = []
        tasks_dir = self.custom_dir / "tasks"
        if not tasks_dir.exists():
            return tasks

        for file in tasks_dir.glob("**/*.py"):
            if file.name == "__init__.py" or file.name.startswith("."):
                continue

            tasks.append(
                {
                    "id": file.stem,
                    "path": str(file),
                    "type": "task",
                    "name": file.stem.replace("_", " ").title(),
                }
            )

        return tasks

    def get_all(self) -> Dict[str, List[Dict[str, Any]]]:
        return {"steps": self.discover_steps(), "tasks": self.discover_tasks()}
