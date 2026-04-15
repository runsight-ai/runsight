from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from runsight_core.yaml.discovery._base import BaseScanner, ScanResult
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

    @property
    def reject_duplicate_entity_ids(self) -> bool:
        return True

    def _parse_file(self, path: Path, raw_yaml: str) -> RunsightWorkflowFile:
        try:
            workflow_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_workflow_file(path, "malformed YAML") from exc

        try:
            workflow_file = RunsightWorkflowFile.model_validate(workflow_data)
        except ValidationError as exc:
            raise _fail_workflow_file(path, str(exc)) from exc

        if workflow_file.id != path.stem:
            raise _fail_workflow_file(
                path,
                f"embedded workflow id '{workflow_file.id}' does not match filename stem '{path.stem}'",
            )

        return workflow_file

    def _scan_yaml_content(
        self, path: Path, raw_yaml: str
    ) -> ScanResult[RunsightWorkflowFile] | None:
        try:
            workflow_data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            raise _fail_workflow_file(path, "malformed YAML") from exc

        if workflow_data is None:
            return None
        if not isinstance(workflow_data, dict):
            raise _fail_workflow_file(path, "YAML content is not a mapping")

        workflow_file = self._parse_file(path, raw_yaml)
        resolved = path.resolve()
        try:
            relative_path = resolved.relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        return ScanResult(
            path=resolved,
            stem=path.stem,
            relative_path=relative_path,
            item=workflow_file,
            aliases=frozenset({workflow_file.id}),
            entity_id=workflow_file.id,
        )

    def resolve_ref(
        self,
        ref: str,
        *,
        index=None,
    ):
        if index is None:
            return None
        return index.get(ref)

    def _glob_yaml_files(self, directory: Path) -> list[Path]:
        candidates = list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml"))
        return sorted(
            {path.resolve(): path for path in candidates}.values(), key=lambda path: path.as_posix()
        )
