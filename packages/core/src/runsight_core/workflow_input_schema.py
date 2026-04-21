from __future__ import annotations

from typing import TypeAlias

from runsight_core.workflow_contract_names import validate_workflow_contract_name
from runsight_core.yaml.schema import (
    InferredWorkflowInputDef,
    InputRef,
    RunsightWorkflowFile,
    WorkflowInputDef,
)

EffectiveWorkflowInputDef: TypeAlias = WorkflowInputDef | InferredWorkflowInputDef
EffectiveWorkflowInputSchema: TypeAlias = dict[str, EffectiveWorkflowInputDef]


def effective_workflow_input_schema(
    file_def: RunsightWorkflowFile,
) -> EffectiveWorkflowInputSchema | None:
    validate_workflow_input_references(file_def)
    if file_def.inputs:
        return dict(file_def.inputs)

    inferred = infer_workflow_input_schema(file_def)
    return inferred or None


def infer_workflow_input_schema(
    file_def: RunsightWorkflowFile,
) -> dict[str, InferredWorkflowInputDef]:
    inferred_types: dict[str, str] = {}
    for from_ref in _iter_declared_from_refs(file_def):
        parsed = _parse_workflow_input_ref(from_ref)
        if parsed is None:
            continue
        name, inferred_type = parsed
        current_type = inferred_types.get(name)
        if current_type == "json" or inferred_type == "json":
            inferred_types[name] = "json"
        else:
            inferred_types[name] = "string"

    return {
        name: InferredWorkflowInputDef(type=inferred_type)
        for name, inferred_type in inferred_types.items()
    }


def validate_workflow_input_references(file_def: RunsightWorkflowFile) -> None:
    explicit_inputs = file_def.inputs
    for from_ref in _iter_declared_from_refs(file_def):
        parsed = _parse_workflow_input_ref(from_ref)
        if parsed is None:
            continue
        name, _inferred_type = parsed
        if explicit_inputs is not None and name not in explicit_inputs:
            raise ValueError(f"workflow input ref '{from_ref}' uses undeclared input '{name}'")


def _iter_declared_from_refs(file_def: RunsightWorkflowFile) -> list[str]:
    refs: list[str] = []
    for block_def in file_def.blocks.values():
        if block_def.inputs is None:
            continue
        for input_ref in block_def.inputs.values():
            refs.append(input_ref.from_ref if isinstance(input_ref, InputRef) else input_ref)
    return refs


def _parse_workflow_input_ref(from_ref: str) -> tuple[str, str] | None:
    parts = from_ref.split(".")
    if parts[0] != "workflow":
        return None
    if len(parts) < 2 or any(part == "" for part in parts):
        raise ValueError(f"workflow input ref '{from_ref}' must include an input name")

    input_name = parts[1]
    validate_workflow_contract_name(input_name)
    inferred_type = "string" if len(parts) == 2 else "json"
    return input_name, inferred_type
