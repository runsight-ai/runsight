"""
WorkflowBlock — execute entire child workflow as a single block step.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import model_validator

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState

if TYPE_CHECKING:
    from runsight_core.workflow import Workflow
    from runsight_core.yaml.registry import WorkflowRegistry
    from runsight_core.yaml.schema import RunsightWorkflowFile, WorkflowInterfaceDef


class WorkflowBlock(BaseBlock):
    """
    Execute entire child workflow as a single block step.

    Implements Hierarchical State Machine (HSM) pattern with:
    - Isolated child state (clean WorkflowState passed to child)
    - Explicit input/output mapping (dotted path resolution)
    - Cycle detection (call_stack tracking)
    - Depth limits (max_depth enforcement)
    - Cost propagation (child metrics added to parent)
    """

    def __init__(
        self,
        block_id: str,
        child_workflow: "Workflow",
        inputs: Dict[str, str],
        outputs: Dict[str, str],
        workflow_ref: Optional[str] = None,
        max_depth: int = 10,
        interface: Optional["WorkflowInterfaceDef"] = None,
        on_error: str = "raise",
    ):
        super().__init__(block_id)
        self.child_workflow = child_workflow
        self.inputs = inputs
        self.outputs = outputs
        self.workflow_ref = workflow_ref
        self.max_depth = max_depth
        self.interface = interface
        self.on_error = on_error

        # Validate: when interface is present, input binding keys must be plain
        # interface names (no dotted child paths).
        if self.interface is not None:
            for binding_name in self.inputs:
                if "." in binding_name:
                    raise ValueError(
                        f"WorkflowBlock '{self.block_id}': input binding key "
                        f"'{binding_name}' contains a dotted path. When an "
                        f"interface is provided, input keys must be plain "
                        f"interface names (e.g. 'topic'), not child dotted "
                        f"paths (e.g. 'shared_memory.topic')."
                    )

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        """Execute WorkflowBlock with BlockContext, return BlockOutput."""
        state: WorkflowState = ctx.state_snapshot
        call_stack: List[str] = ctx.inputs.get("call_stack") or []
        workflow_registry = ctx.inputs.get("workflow_registry")
        observer = ctx.inputs.get("observer")

        # Step 1: Cycle detection
        if self.child_workflow.name in call_stack:
            raise RecursionError(
                f"WorkflowBlock '{self.block_id}': cycle detected. "
                f"Workflow '{self.child_workflow.name}' is already in call stack. "
                f"Call stack: {' -> '.join(call_stack)} -> {self.child_workflow.name}"
            )

        # Step 2: Depth check
        if len(call_stack) >= self.max_depth:
            raise RecursionError(
                f"WorkflowBlock '{self.block_id}': maximum depth {self.max_depth} exceeded. "
                f"Call stack depth: {len(call_stack)}. "
                f"Call stack: {' -> '.join(call_stack)}"
            )

        # Step 3: Map inputs (parent -> child)
        child_state = self._map_inputs(state, self.inputs)

        # Step 4: Run child workflow
        from runsight_core.observer import build_child_observer

        child_observer = None
        child_run_id = None
        if observer:
            child_observer, child_run_id = build_child_observer(observer, block_id=self.block_id)

        start_time = time.monotonic()
        try:
            child_final_state = await self.child_workflow.run(
                child_state,
                call_stack=call_stack + [self.child_workflow.name],
                workflow_registry=workflow_registry,
                observer=child_observer,
            )
        except Exception as exc:
            duration_s = time.monotonic() - start_time
            if self.on_error != "catch":
                raise
            return BlockOutput(
                output=f"WorkflowBlock '{self.child_workflow.name}' failed",
                exit_handle="error",
                cost_usd=0.0,
                total_tokens=0,
                metadata={
                    "child_status": "failed",
                    "child_error": str(exc),
                    "child_cost_usd": 0.0,
                    "child_tokens": 0,
                    "child_duration_s": round(duration_s, 4),
                    "child_run_id": child_run_id,
                },
                log_entries=[
                    {
                        "role": "system",
                        "content": (
                            f"[Block {self.block_id}] WorkflowBlock '{self.child_workflow.name}' "
                            f"failed (on_error=catch): {exc}"
                        ),
                    }
                ],
            )
        duration_s = time.monotonic() - start_time

        # Step 4b: Soft failures
        if self.on_error == "catch":
            for _bid, _br in child_final_state.results.items():
                if isinstance(_br, BlockResult) and _br.exit_handle == "error":
                    return BlockOutput(
                        output=f"WorkflowBlock '{self.child_workflow.name}' failed",
                        exit_handle="error",
                        cost_usd=0.0,
                        total_tokens=0,
                        metadata={
                            "child_status": "failed",
                            "child_error": _br.output,
                            "child_cost_usd": child_final_state.total_cost_usd,
                            "child_tokens": child_final_state.total_tokens,
                            "child_duration_s": round(duration_s, 4),
                            "child_run_id": child_run_id,
                        },
                        log_entries=[
                            {
                                "role": "system",
                                "content": (
                                    f"[Block {self.block_id}] WorkflowBlock "
                                    f"'{self.child_workflow.name}' "
                                    f"failed (on_error=catch, soft error in block '{_bid}')"
                                ),
                            }
                        ],
                    )

        # Step 5: Collect output mappings as extra_results / shared_memory_updates
        extra_results: Dict[str, Any] = {}
        shared_memory_updates: Dict[str, Any] = {}

        if self.interface is not None:
            output_lookup = {odef.name: odef.source for odef in self.interface.outputs}
            for parent_path, interface_name in self.outputs.items():
                source = output_lookup.get(interface_name)
                if source is None:
                    raise ValueError(
                        f"WorkflowBlock '{self.block_id}': output binding "
                        f"'{interface_name}' does not match any interface output."
                    )
                value = self._resolve_dotted(child_final_state, source, context="child state")
                parts = parent_path.split(".", 1)
                if parts[0] == "results" and len(parts) == 2:
                    # Unwrap BlockResult to its .output string, matching legacy _map_outputs behavior.
                    if isinstance(value, BlockResult):
                        value = value.output
                    extra_results[parts[1]] = value
                elif parts[0] == "shared_memory" and len(parts) == 2:
                    if isinstance(value, BlockResult):
                        value = value.output
                    shared_memory_updates[parts[1]] = value
        else:
            for parent_path, child_path in self.outputs.items():
                value = self._resolve_dotted(child_final_state, child_path, context="child state")
                parts = parent_path.split(".", 1)
                if parts[0] == "results" and len(parts) == 2:
                    # No-interface path: store value as-is (BlockResult or raw), matching legacy behavior.
                    extra_results[parts[1]] = value
                elif parts[0] == "shared_memory" and len(parts) == 2:
                    if isinstance(value, BlockResult):
                        value = value.output
                    shared_memory_updates[parts[1]] = value

        child_metadata = {
            "child_status": "completed",
            "child_cost_usd": child_final_state.total_cost_usd,
            "child_tokens": child_final_state.total_tokens,
            "child_duration_s": round(duration_s, 4),
            "child_run_id": child_run_id,
        }

        return BlockOutput(
            output=f"WorkflowBlock '{self.child_workflow.name}' completed",
            exit_handle="completed",
            cost_usd=child_final_state.total_cost_usd,
            total_tokens=child_final_state.total_tokens,
            metadata=child_metadata,
            log_entries=[
                {
                    "role": "system",
                    "content": (
                        f"[Block {self.block_id}] WorkflowBlock '{self.child_workflow.name}' "
                        f"completed (cost: ${child_final_state.total_cost_usd:.4f}, "
                        f"tokens: {child_final_state.total_tokens})"
                    ),
                }
            ],
            extra_results=extra_results if extra_results else None,
            shared_memory_updates=shared_memory_updates if shared_memory_updates else None,
        )

    def _resolve_dotted(self, state: WorkflowState, path: str, *, context: str = "state") -> Any:
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': path '{path}' is deprecated. "
                f"current_task is no longer supported in dotted path resolution. "
                f"Use results.* or shared_memory.* instead."
            )

        elif field in ("results", "shared_memory", "metadata"):
            if len(parts) != 2:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"Expected format: '{field}.key', got '{path}'."
                )
            key = parts[1]
            field_dict = getattr(state, field)

            if key not in field_dict:
                raise KeyError(
                    f"WorkflowBlock '{self.block_id}': path '{path}' not found in {context}. "
                    f"Available {field} keys: {sorted(field_dict.keys())}"
                )
            return field_dict[key]

        else:
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': invalid path prefix '{field}'. "
                f"Supported prefixes: results, shared_memory, metadata."
            )

    def _write_dotted(self, state: WorkflowState, path: str, value: Any) -> WorkflowState:
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': path '{path}' is deprecated. "
                f"current_task is no longer supported in dotted path resolution. "
                f"Use results.* or shared_memory.* instead."
            )

        elif field in ("results", "shared_memory", "metadata"):
            if len(parts) != 2:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"Expected format: '{field}.key', got '{path}'."
                )
            key = parts[1]
            field_dict = getattr(state, field)
            new_dict = {**field_dict, key: value}
            return state.model_copy(update={field: new_dict})

        else:
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': invalid path prefix '{field}'. "
                f"Supported prefixes: results, shared_memory, metadata."
            )

    def _map_inputs(
        self,
        parent_state: WorkflowState,
        inputs: Dict[str, str],
    ) -> WorkflowState:
        child_state = WorkflowState(artifact_store=parent_state.artifact_store)

        if self.interface is not None:
            # Interface-mediated: keys are interface names, resolve via target
            input_lookup = {idef.name: idef.target for idef in self.interface.inputs}
            for interface_name, parent_path in inputs.items():
                target = input_lookup.get(interface_name)
                if target is None:
                    raise ValueError(
                        f"WorkflowBlock '{self.block_id}': input binding "
                        f"'{interface_name}' does not match any interface input."
                    )
                value = self._resolve_dotted(parent_state, parent_path, context="parent state")
                if isinstance(value, BlockResult):
                    value = value.output
                child_state = self._write_dotted(child_state, target, value)
        else:
            # Legacy: keys are child dotted paths directly
            for child_key, parent_path in inputs.items():
                value = self._resolve_dotted(parent_state, parent_path, context="parent state")
                child_state = self._write_dotted(child_state, child_key, value)

        return child_state

    def _map_outputs(
        self,
        parent_state: WorkflowState,
        child_final_state: WorkflowState,
        outputs: Dict[str, str],
    ) -> WorkflowState:
        new_parent = parent_state

        if self.interface is not None:
            # Interface-mediated: values are interface names, resolve via source
            output_lookup = {odef.name: odef.source for odef in self.interface.outputs}
            for parent_path, interface_name in outputs.items():
                source = output_lookup.get(interface_name)
                if source is None:
                    raise ValueError(
                        f"WorkflowBlock '{self.block_id}': output binding "
                        f"'{interface_name}' does not match any interface output."
                    )
                value = self._resolve_dotted(child_final_state, source, context="child state")
                if isinstance(value, BlockResult):
                    value = value.output
                new_parent = self._write_dotted(new_parent, parent_path, value)
        else:
            # Legacy: values are child dotted paths directly
            for parent_path, child_path in outputs.items():
                value = self._resolve_dotted(child_final_state, child_path, context="child state")
                new_parent = self._write_dotted(new_parent, parent_path, value)

        return new_parent


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class WorkflowBlockDef(BaseBlockDef):
    """
    WorkflowBlock definition.

    ``inputs`` and ``outputs`` override BaseBlockDef fields with workflow-specific
    types (Dict[str, str] for state key mapping) to maintain backward compatibility
    with existing YAML files and parser code that accesses ``block_def.inputs``.
    """

    type: Literal["workflow"] = "workflow"
    workflow_ref: str
    inputs: Optional[Dict[str, str]] = None  # type: ignore[assignment]  # child_state_key -> parent_path
    outputs: Optional[Dict[str, str]] = None  # parent_path -> child_dotted_path
    max_depth: Optional[int] = None
    on_error: Literal["raise", "catch"] = "raise"

    @model_validator(mode="after")
    def _validate_interface_bindings(self) -> "WorkflowBlockDef":
        for binding_name in (self.inputs or {}).keys():
            if "." in binding_name:
                raise ValueError(
                    "workflow block inputs must bind child interface names, not child dotted paths"
                )

        for binding_name in (self.outputs or {}).values():
            if "." in binding_name:
                raise ValueError(
                    "workflow block outputs must bind child interface names, not child dotted paths"
                )

        return self


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("workflow", WorkflowBlockDef)


def _validate_workflow_block_contract(
    block_id: str,
    block_def: Any,
    child_file: "RunsightWorkflowFile",
) -> None:
    child_interface = child_file.interface
    if child_interface is None:
        raise ValueError(
            f"WorkflowBlock '{block_id}': child workflow '{block_def.workflow_ref}' "
            "must declare an interface"
        )

    declared_inputs = {item.name: item for item in child_interface.inputs}
    declared_outputs = {item.name for item in child_interface.outputs}

    for binding_name in (block_def.inputs or {}).keys():
        if binding_name not in declared_inputs:
            raise ValueError(
                f"WorkflowBlock '{block_id}': unknown interface input '{binding_name}'. "
                f"Declared child inputs: {sorted(declared_inputs)}"
            )

    missing_required = [
        item.name
        for item in child_interface.inputs
        if item.required and item.default is None and item.name not in (block_def.inputs or {})
    ]
    if missing_required:
        raise ValueError(
            f"WorkflowBlock '{block_id}': missing required interface inputs {missing_required}"
        )

    for binding_name in (block_def.outputs or {}).values():
        if binding_name not in declared_outputs:
            raise ValueError(
                f"WorkflowBlock '{block_id}': unknown interface output '{binding_name}'. "
                f"Declared child outputs: {sorted(declared_outputs)}"
            )


def _resolve_workflow_block_max_depth(
    file_def: Any,
    block_def: Any,
) -> int:
    """Resolve the max_depth value a workflow block will enforce at runtime."""
    if block_def.max_depth is not None:
        return block_def.max_depth
    return file_def.config.get("max_workflow_depth", 10)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    *,
    workflow_registry: "WorkflowRegistry" | None = None,
    api_keys: Dict[str, str] | None = None,
    workflow_base_dir: str = ".",
    parent_file_def: Any | None = None,
    **_: Any,
) -> WorkflowBlock:
    """Build a WorkflowBlock from a block definition."""
    if getattr(block_def, "workflow_ref", None) is None:
        raise ValueError(f"WorkflowBlock '{block_id}': workflow_ref is required")
    if workflow_registry is None:
        raise ValueError(
            f"WorkflowBlock '{block_id}': workflow_registry must be provided "
            "when building workflow blocks"
        )

    # Import the parser lazily to keep block registration free of parser cycles.
    from runsight_core.yaml.parser import parse_workflow_yaml

    child_file = workflow_registry.get(block_def.workflow_ref)
    _validate_workflow_block_contract(block_id, block_def, child_file)

    child_raw = child_file.model_dump() if hasattr(child_file, "model_dump") else child_file
    child_wf = parse_workflow_yaml(
        child_raw,
        workflow_registry=workflow_registry,
        api_keys=api_keys,
        _base_dir=workflow_base_dir,
    )

    max_depth = (
        _resolve_workflow_block_max_depth(parent_file_def, block_def)
        if parent_file_def is not None
        else block_def.max_depth or 10
    )
    return WorkflowBlock(
        block_id=block_id,
        child_workflow=child_wf,
        inputs=block_def.inputs or {},
        outputs=block_def.outputs or {},
        workflow_ref=block_def.workflow_ref,
        max_depth=max_depth,
        interface=child_file.interface,
        on_error=block_def.on_error,
    )


_register_builder("workflow", build)
