"""Reusable runnable workflow registry construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from runsight_core.yaml.discovery import WorkflowScanner
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def build_runnable_workflow_registry(
    *,
    base_path: Path,
    workflow_id: str,
    raw_yaml: str,
    root_path: Path,
    git_ref: str | None = None,
    git_service: Any = None,
) -> WorkflowRegistry:
    """Build a registry for nested workflow execution from a root YAML snapshot."""
    data = yaml.safe_load(raw_yaml)
    if not isinstance(data, dict):
        raise ValueError("YAML content is not a mapping")

    root_file = RunsightWorkflowFile.model_validate(data)
    if root_file.id != workflow_id:
        raise ValueError(
            f"embedded workflow id {root_file.id!r} does not match requested workflow:{workflow_id}"
        )
    registry = WorkflowRegistry()
    workflow_index = WorkflowScanner(base_path).scan(git_ref=git_ref, git_service=git_service)
    workflow_results_by_id = {
        result.entity_id: result
        for result in workflow_index.get_all()
        if result.entity_id is not None
    }

    validation_index: dict[str, tuple[Path, RunsightWorkflowFile]] = {}
    root_ref = root_file.id
    resolved_root = root_path.resolve()
    registry.register(root_ref, root_file)
    validation_index[root_ref] = (resolved_root, root_file)

    pending: list[RunsightWorkflowFile] = [root_file]
    loaded_paths = {str(resolved_root)}

    while pending:
        current_file = pending.pop()
        for block_def in current_file.blocks.values():
            if block_def.type != "workflow":
                continue

            resolved_child = workflow_results_by_id.get(block_def.workflow_ref)
            if resolved_child is None:
                continue

            child_path = resolved_child.path
            child_ref = str(child_path)
            if child_ref in loaded_paths:
                continue

            loaded_paths.add(child_ref)
            child_id = resolved_child.entity_id
            registry.register(child_id, resolved_child.item)
            validation_index[child_id] = (child_path, resolved_child.item)
            pending.append(resolved_child.item)

    validate_workflow_call_contracts(
        root_file,
        base_dir=str(base_path),
        validation_index=validation_index,
        current_workflow_ref=root_ref,
    )
    return registry
