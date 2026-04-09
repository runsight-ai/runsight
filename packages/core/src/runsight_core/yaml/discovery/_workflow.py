from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError
from runsight_core.yaml.discovery._base import BaseScanner
from runsight_core.yaml.schema import RunsightWorkflowFile


def _fail_workflow_file(yaml_file: Path, message: str) -> ValueError:
    return ValueError(f"{yaml_file.name}: {message}")


class WorkflowScanner(BaseScanner[RunsightWorkflowFile]):
    """Scanner for workflow YAML files."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        workflows_subdir: str = "custom/workflows",
    ) -> None:
        super().__init__(base_dir)
        self._workflows_subdir = workflows_subdir

    @property
    def asset_subdir(self) -> str:
        return self._workflows_subdir

    def _parse_file(self, path: Path, raw_yaml: str) -> RunsightWorkflowFile:
        try:
            workflow_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_workflow_file(path, "malformed YAML") from exc

        try:
            return RunsightWorkflowFile.model_validate(workflow_data)
        except ValidationError as exc:
            raise _fail_workflow_file(path, str(exc)) from exc

    def _compute_aliases(self, path: Path, item: RunsightWorkflowFile) -> set[str]:
        aliases = super()._compute_aliases(path, item)
        workflow_name = getattr(item.workflow, "name", None)
        if isinstance(workflow_name, str) and workflow_name.strip():
            aliases.add(workflow_name)
        return aliases

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        candidates = list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml"))
        return sorted(
            {path.resolve(): path for path in candidates}.values(), key=lambda path: path.as_posix()
        )
