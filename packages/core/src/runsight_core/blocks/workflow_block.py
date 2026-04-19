"""
WorkflowBlock — execute entire child workflow as a single block step.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import copy
import time
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import model_validator

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.redaction import RunRedactor
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow_contract_names import validate_workflow_contract_name

if TYPE_CHECKING:
    from runsight_core.workflow import Workflow
    from runsight_core.yaml.registry import WorkflowRegistry
    from runsight_core.yaml.schema import RunsightWorkflowFile


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
        interface: Any = None,
        on_error: str = "raise",
    ):
        super().__init__(block_id)
        if interface is not None:
            raise ValueError("legacy workflow interface is unsupported")
        self.child_workflow = child_workflow
        self.inputs = inputs
        self.outputs = outputs
        self.workflow_ref = workflow_ref
        self.max_depth = max_depth
        self.interface = None
        self.on_error = on_error

        for binding_name in self.inputs:
            self._validate_child_invocation_input_name(binding_name)
        for child_source_path in self.outputs.values():
            self._validate_child_output_source_path(child_source_path)

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

        # Step 3: Map parent values to public child invocation inputs.
        child_inputs = self._map_inputs_from_context(ctx.inputs)
        child_inputs = self._apply_child_input_defaults(child_inputs)
        child_redactor = self._register_child_sensitive_inputs(state.input_redactor, child_inputs)
        child_state = WorkflowState(
            workflow_inputs=dict(child_inputs),
            artifact_store=state.artifact_store,
            input_redactor=child_redactor,
        )

        # Step 4: Run child workflow
        from runsight_core.observer import build_child_observer

        child_observer = None
        child_run_id = None
        if observer:
            if self._observer_has_terminal_hooks(observer):
                child_observer, child_run_id = build_child_observer(
                    observer, block_id=self.block_id
                )
            else:
                child_observer = observer
        self._record_child_workflow_input_snapshot(child_observer, child_inputs)

        start_time = time.monotonic()
        try:
            child_final_state = await self.child_workflow.run(
                child_state,
                call_stack=call_stack + [self.child_workflow.name],
                workflow_registry=workflow_registry,
                observer=child_observer,
                inputs=child_inputs,
            )
        except Exception as exc:
            duration_s = time.monotonic() - start_time
            if self.on_error != "catch":
                raise
            child_redactor = self._promote_child_sensitive_inputs(child_redactor, child_inputs)
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
                input_redactor=child_redactor,
            )
        duration_s = time.monotonic() - start_time
        child_redactor = self._promote_child_sensitive_inputs(
            child_final_state.input_redactor or child_redactor,
            child_inputs,
        )

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
                        input_redactor=child_redactor,
                    )

        # Step 5: Collect output mappings as extra_results / shared_memory_updates
        extra_results: Dict[str, Any] = {}
        shared_memory_updates: Dict[str, Any] = {}

        for parent_path, child_path in self.outputs.items():
            value = self._resolve_dotted(child_final_state, child_path, context="child state")
            parts = parent_path.split(".", 1)
            if parts[0] == "results" and len(parts) == 2:
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
            input_redactor=child_redactor,
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
    ) -> Dict[str, Any]:
        child_inputs: Dict[str, Any] = {}
        for input_name, parent_path in inputs.items():
            self._validate_child_invocation_input_name(input_name)
            value = self._resolve_dotted(parent_state, parent_path, context="parent state")
            if isinstance(value, BlockResult):
                value = value.output
            child_inputs[input_name] = value
        return child_inputs

    def _map_inputs_from_context(
        self,
        resolved_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        child_inputs: Dict[str, Any] = {}
        for input_name in self.inputs:
            self._validate_child_invocation_input_name(input_name)
            child_inputs[input_name] = self._require_governed_input(resolved_inputs, input_name)
        return child_inputs

    def _apply_child_input_defaults(self, child_inputs: Dict[str, Any]) -> Dict[str, Any]:
        input_schema = getattr(self.child_workflow, "input_schema", None) or {}
        resolved_inputs = dict(child_inputs)
        for name, input_def in input_schema.items():
            if name not in resolved_inputs and getattr(input_def, "default", None) is not None:
                resolved_inputs[name] = copy.deepcopy(input_def.default)
        return resolved_inputs

    def _record_child_workflow_input_snapshot(
        self,
        observer: Any,
        child_inputs: Dict[str, Any],
    ) -> None:
        recorder = getattr(observer, "record_workflow_input_snapshot", None)
        if callable(recorder):
            recorder(getattr(self.child_workflow, "input_schema", None) or {}, child_inputs)

    def _validate_child_invocation_input_name(self, input_name: str) -> str:
        if "." in input_name:
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': input binding '{input_name}' targets "
                "private child state. Bind a child invocation input name instead."
            )
        return validate_workflow_contract_name(input_name)

    def _validate_child_output_source_path(self, source_path: str) -> str:
        return _validate_child_output_source_path(source_path, block_id=self.block_id)

    def _require_governed_input(self, resolved_inputs: Dict[str, Any], input_name: str) -> Any:
        if input_name not in resolved_inputs:
            raise KeyError(
                f"WorkflowBlock '{self.block_id}': governed input '{input_name}' is missing "
                "from BlockContext inputs. WorkflowBlock inputs must be resolved by "
                "context governance before execution."
            )
        return resolved_inputs[input_name]

    def _register_child_sensitive_inputs(
        self,
        redactor: RunRedactor | None,
        child_inputs: Dict[str, Any],
    ) -> RunRedactor | None:
        input_schema = getattr(self.child_workflow, "input_schema", None) or {}
        for name, input_def in input_schema.items():
            if not getattr(input_def, "sensitive", False) or name not in child_inputs:
                continue
            if redactor is None:
                redactor = RunRedactor()
            redactor.register_named(name, child_inputs[name])
        return redactor

    def _promote_child_sensitive_inputs(
        self,
        redactor: RunRedactor | None,
        child_inputs: Dict[str, Any],
    ) -> RunRedactor | None:
        input_schema = getattr(self.child_workflow, "input_schema", None) or {}
        for name, input_def in input_schema.items():
            if not getattr(input_def, "sensitive", False) or name not in child_inputs:
                continue
            if redactor is None:
                redactor = RunRedactor()
            redactor.register(child_inputs[name])
        return redactor

    @staticmethod
    def _observer_has_terminal_hooks(observer: Any) -> bool:
        return callable(getattr(observer, "on_workflow_complete", None)) or callable(
            getattr(observer, "on_workflow_error", None)
        )


def _validate_child_output_source_path(source_path: str, *, block_id: str | None = None) -> str:
    if not isinstance(source_path, str):
        raise ValueError("workflow block output child source path must be a string")

    prefix = f"WorkflowBlock '{block_id}': " if block_id is not None else ""
    field, sep, key = source_path.partition(".")
    if not sep or not key:
        raise ValueError(
            f"{prefix}workflow block outputs must use a dotted child source path; "
            "public output contract names are unsupported in this ticket"
        )
    if field not in {"results", "shared_memory", "metadata"}:
        raise ValueError(
            f"{prefix}workflow block output child source path '{source_path}' must start "
            "with results., shared_memory., or metadata."
        )
    return source_path


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
                    "workflow block inputs must bind child interface names, not dotted child paths"
                )
            validate_workflow_contract_name(binding_name)

        for binding_name in (self.outputs or {}).values():
            _validate_child_output_source_path(binding_name)

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
    for binding_name in (block_def.inputs or {}).keys():
        if "." in binding_name:
            raise ValueError(
                f"WorkflowBlock '{block_id}': input binding '{binding_name}' targets "
                "private child state. Bind a child invocation input name instead."
            )
        validate_workflow_contract_name(binding_name)

    for binding_name in (block_def.outputs or {}).values():
        _validate_child_output_source_path(binding_name, block_id=block_id)


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
        on_error=block_def.on_error,
    )


_register_builder("workflow", build)
