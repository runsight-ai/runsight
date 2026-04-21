"""Workflow YAML validation and governance helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from pydantic import ValidationError as PydanticValidationError
from runsight_core.identity import EntityKind, EntityRef, validate_entity_id
from runsight_core.yaml.discovery import SoulScanner
from runsight_core.yaml.schema import RunsightWorkflowFile

from ...domain.errors import InputValidationError


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


def assert_valid_yaml_for_write(workflow_id: str, raw_yaml: str) -> None:
    """Validate YAML authoring invariants for create/update/patch writes."""
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise InputValidationError("Malformed YAML") from exc
    if not isinstance(data, dict):
        raise InputValidationError("YAML content is not a mapping")
    embedded_id = data.get("id")
    if not isinstance(embedded_id, str) or not embedded_id:
        raise InputValidationError("Workflow must have an id")
    kind = data.get("kind")
    if kind != "workflow":
        raise InputValidationError("kind must be 'workflow'")
    try:
        validate_entity_id(embedded_id, EntityKind.WORKFLOW)
    except ValueError as exc:
        raise InputValidationError(str(exc)) from exc
    if embedded_id != workflow_id:
        raise InputValidationError(
            f"embedded workflow id {embedded_id!r} does not match requested "
            f"{_workflow_ref(workflow_id)}"
        )


def validate_yaml_content(
    *,
    base_path: Path,
    workflow_id: str,
    raw_yaml: Optional[str],
    registry_builder: Callable[..., Any],
    declared_tool_definitions_validator: Callable[..., Any],
    tool_governance_validator: Callable[..., Any],
    has_workflow_blocks: Callable[[RunsightWorkflowFile], bool],
) -> tuple[bool, Optional[str], list[dict[str, Optional[str]]]]:
    """Validate raw YAML into the repository entity-facing result shape."""
    if not raw_yaml:
        return False, "No YAML content to validate", []

    warnings: list[dict[str, Optional[str]]] = []
    try:
        data = yaml.safe_load(raw_yaml)
        if not isinstance(data, dict):
            return False, "YAML content is not a mapping", []

        file_def = RunsightWorkflowFile.model_validate(data)
        souls_map = SoulScanner(base_path).scan().ids()
        validation_result = tool_governance_validator(file_def, souls_map)
        validation_result.merge(
            declared_tool_definitions_validator(
                file_def,
                base_dir=str(base_path),
                require_custom_metadata=True,
            )
        )
        warnings = validation_result.warnings_as_dicts()
        if validation_result.has_errors:
            return (
                False,
                validation_result.error_summary or "Tool governance validation failed",
                warnings,
            )

        if has_workflow_blocks(file_def):
            try:
                registry_builder(workflow_id, raw_yaml)
            except ValueError as exc:
                return False, str(exc), warnings

        return True, None, warnings
    except PydanticValidationError as exc:
        return False, str(exc), []
    except ValueError as exc:
        return False, str(exc), warnings
    except Exception as exc:
        return False, f"Unexpected validation error: {exc}", warnings
