"""
WorkflowBlock — execute entire child workflow as a single block step.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import model_validator

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState

if TYPE_CHECKING:
    from runsight_core.workflow import Workflow
    from runsight_core.yaml.registry import WorkflowRegistry
    from runsight_core.yaml.schema import WorkflowInterfaceDef


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
        max_depth: int = 10,
        interface: Optional["WorkflowInterfaceDef"] = None,
        on_error: str = "raise",
    ):
        super().__init__(block_id)
        self.child_workflow = child_workflow
        self.inputs = inputs
        self.outputs = outputs
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

    async def execute(
        self,
        state: WorkflowState,
        *,
        call_stack: Optional[List[str]] = None,
        workflow_registry: Optional["WorkflowRegistry"] = None,
        **kwargs,
    ) -> WorkflowState:
        call_stack = call_stack or []

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

        # Step 4: Run child workflow (propagate observer for monitoring)
        from runsight_core.observer import ChildObserverWrapper

        parent_observer = kwargs.get("observer")
        observer = ChildObserverWrapper(parent_observer) if parent_observer else None
        start_time = time.monotonic()
        try:
            child_final_state = await self.child_workflow.run(
                child_state,
                call_stack=call_stack + [self.child_workflow.name],
                workflow_registry=workflow_registry,
                observer=observer,
            )
        except Exception as exc:
            duration_s = time.monotonic() - start_time
            if self.on_error != "catch":
                raise
            # on_error="catch": swallow exception, skip output mapping,
            # return parent state with an error BlockResult.
            child_metadata = {
                "child_status": "failed",
                "child_error": str(exc),
                "child_cost_usd": 0,
                "child_tokens": 0,
                "child_duration_s": round(duration_s, 4),
                "child_run_id": None,
            }
            return state.model_copy(
                update={
                    "results": {
                        **state.results,
                        self.block_id: BlockResult(
                            output=f"WorkflowBlock '{self.child_workflow.name}' failed",
                            exit_handle="error",
                            metadata=child_metadata,
                        ),
                    },
                    "execution_log": state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": (
                                f"[Block {self.block_id}] WorkflowBlock '{self.child_workflow.name}' "
                                f"failed (on_error=catch): {exc}"
                            ),
                        }
                    ],
                }
            )
        duration_s = time.monotonic() - start_time

        # Step 4b: Detect soft failures in child results (blocks that captured
        # errors into BlockResults with exit_handle="error" rather than raising).
        if self.on_error == "catch":
            for _bid, _br in child_final_state.results.items():
                if isinstance(_br, BlockResult) and _br.exit_handle == "error":
                    child_metadata = {
                        "child_status": "failed",
                        "child_error": _br.output,
                        "child_cost_usd": child_final_state.total_cost_usd,
                        "child_tokens": child_final_state.total_tokens,
                        "child_duration_s": round(duration_s, 4),
                        "child_run_id": None,
                    }
                    return state.model_copy(
                        update={
                            "results": {
                                **state.results,
                                self.block_id: BlockResult(
                                    output=f"WorkflowBlock '{self.child_workflow.name}' failed",
                                    exit_handle="error",
                                    metadata=child_metadata,
                                ),
                            },
                            "execution_log": state.execution_log
                            + [
                                {
                                    "role": "system",
                                    "content": (
                                        f"[Block {self.block_id}] WorkflowBlock "
                                        f"'{self.child_workflow.name}' "
                                        f"failed (on_error=catch, soft error in block '{_bid}')"
                                    ),
                                }
                            ],
                        }
                    )

        # Step 5: Merge child results into parent, then apply output mappings
        merged_parent = state.model_copy(
            update={
                "results": {**state.results, **child_final_state.results},
            }
        )
        new_parent_state = self._map_outputs(merged_parent, child_final_state, self.outputs)

        # Step 6: Propagate costs and add system message with compact metadata
        child_metadata = {
            "child_status": "completed",
            "child_cost_usd": child_final_state.total_cost_usd,
            "child_tokens": child_final_state.total_tokens,
            "child_duration_s": round(duration_s, 4),
            "child_run_id": None,
        }

        return new_parent_state.model_copy(
            update={
                "results": {
                    **new_parent_state.results,
                    self.block_id: BlockResult(
                        output=f"WorkflowBlock '{self.child_workflow.name}' completed",
                        exit_handle="completed",
                        metadata=child_metadata,
                    ),
                },
                "execution_log": new_parent_state.execution_log
                + [
                    {
                        "role": "system",
                        "content": (
                            f"[Block {self.block_id}] WorkflowBlock '{self.child_workflow.name}' "
                            f"completed (cost: ${child_final_state.total_cost_usd:.4f}, "
                            f"tokens: {child_final_state.total_tokens})"
                        ),
                    }
                ],
                "total_cost_usd": new_parent_state.total_cost_usd
                + child_final_state.total_cost_usd,
                "total_tokens": new_parent_state.total_tokens + child_final_state.total_tokens,
            }
        )

    def _resolve_dotted(self, state: WorkflowState, path: str, *, context: str = "state") -> Any:
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            if len(parts) > 1:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"current_task does not support nested access."
                )
            return state.current_task

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
                f"Supported prefixes: current_task, results, shared_memory, metadata."
            )

    def _write_dotted(self, state: WorkflowState, path: str, value: Any) -> WorkflowState:
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            if len(parts) > 1:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"current_task does not support nested access."
                )
            return state.model_copy(update={"current_task": value})

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
                f"Supported prefixes: current_task, results, shared_memory, metadata."
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


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> WorkflowBlock:
    """Build a WorkflowBlock from a block definition.

    Note: In practice, the workflow block is handled as a special case in
    parse_workflow_yaml because it requires a WorkflowRegistry for recursive
    parsing. This build() function exists for API consistency and can be
    used when the child_workflow is already resolved.
    """
    raise NotImplementedError(
        f"WorkflowBlock '{block_id}' must be built via the special-case "
        f"handler in parse_workflow_yaml, not via the generic builder registry."
    )


_register_builder("workflow", build)
