"""Workflow entity assembly from persisted YAML and sidecars."""

from __future__ import annotations

from typing import Any, Callable, Optional

from ...domain.value_objects import WorkflowEntity


def build_workflow_entity(
    *,
    data: dict[str, Any],
    stem: str,
    validate_yaml_content: Callable[
        [str, Optional[str]], tuple[bool, Optional[str], list[dict[str, Optional[str]]]]
    ],
    canvas_state: Optional[dict[str, Any]] = None,
    raw_yaml: Optional[str] = None,
    extra_warnings: Optional[list[dict[str, Optional[str]]]] = None,
) -> WorkflowEntity:
    """Build a WorkflowEntity, preserving embedded-id semantics and warnings."""
    entity_id = data.get("id")
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError(f"{stem}.yaml: missing required id")
    if entity_id != stem:
        raise ValueError(
            f"{stem}.yaml: embedded id '{entity_id}' does not match filename stem '{stem}'"
        )

    valid, validation_error, warnings = validate_yaml_content(stem, raw_yaml)
    if extra_warnings:
        warnings = [*warnings, *extra_warnings]

    entity_data = dict(data)
    entity_data["yaml"] = raw_yaml
    entity_data["valid"] = valid
    entity_data["validation_error"] = validation_error
    entity_data["warnings"] = warnings
    entity_data["filename"] = f"{stem}.yaml"
    if canvas_state is not None:
        entity_data["canvas_state"] = canvas_state

    workflow_section = data.get("workflow")
    if isinstance(workflow_section, dict) and workflow_section.get("name"):
        entity_data["name"] = workflow_section["name"]

    return WorkflowEntity(**entity_data)
