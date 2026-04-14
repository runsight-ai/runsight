"""
BlockContext and BlockOutput models, apply_block_output, and build_block_context for RUN-883/RUN-884.
"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from runsight_core.artifacts import ArtifactStore
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState


class BlockContext(BaseModel):
    """Input context passed to a block during execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    block_id: str
    instruction: str
    context: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    conversation_history: List[Dict] = Field(default_factory=list)
    soul: Optional[Soul] = None
    model_name: Optional[str] = None
    artifact_store: Optional[ArtifactStore] = None
    state_snapshot: Optional[WorkflowState] = None

    @field_validator("conversation_history", mode="before")
    @classmethod
    def copy_conversation_history(cls, v: Any) -> Any:
        if isinstance(v, list):
            return list(v)
        return v


class BlockOutput(BaseModel):
    """Output produced by a block after execution."""

    output: str
    exit_handle: Optional[str] = None
    artifact_ref: Optional[str] = None
    artifact_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    total_tokens: int = 0
    log_entries: List[Dict[str, str]] = Field(default_factory=list)
    conversation_updates: Optional[Dict[str, List[Dict]]] = None
    shared_memory_updates: Optional[Dict[str, Any]] = None
    extra_results: Optional[Dict[str, Any]] = None


def apply_block_output(state: WorkflowState, block_id: str, output: BlockOutput) -> WorkflowState:
    """Apply a BlockOutput to a WorkflowState, returning a new WorkflowState.

    Creates a new WorkflowState with the block result stored, cost/tokens accumulated,
    execution log extended, and optional shared_memory, conversation_histories, and
    extra_results merged in.
    """
    new_result = BlockResult(
        output=output.output,
        exit_handle=output.exit_handle,
        artifact_ref=output.artifact_ref,
        artifact_type=output.artifact_type,
        metadata=output.metadata if output.metadata else None,
    )

    new_results = {**state.results, block_id: new_result}
    if output.extra_results:
        new_results.update(output.extra_results)

    new_shared_memory = dict(state.shared_memory)
    if output.shared_memory_updates is not None:
        new_shared_memory.update(output.shared_memory_updates)

    new_execution_log = list(state.execution_log) + list(output.log_entries)

    new_conversation_histories = dict(state.conversation_histories)
    if output.conversation_updates is not None:
        for key, messages in output.conversation_updates.items():
            existing = list(new_conversation_histories.get(key, []))
            existing.extend(messages)
            new_conversation_histories[key] = existing

    return state.model_copy(
        update={
            "results": new_results,
            "total_cost_usd": state.total_cost_usd + output.cost_usd,
            "total_tokens": state.total_tokens + output.total_tokens,
            "execution_log": new_execution_log,
            "shared_memory": new_shared_memory,
            "conversation_histories": new_conversation_histories,
        }
    )


def _resolve_ref(from_ref: str, state: WorkflowState) -> Any:
    """Resolve 'source_id' or 'source_id.field.path' against state.results.

    Replicates Step._resolve_from_ref logic exactly.
    """
    parts = from_ref.split(".", 1)
    source_id = parts[0]
    if source_id not in state.results:
        raise ValueError(
            f"Input resolution failed: source block '{source_id}' not found in state.results. "
            f"Available: {sorted(state.results.keys())}"
        )
    raw = state.results[source_id]
    if isinstance(raw, BlockResult):
        raw = raw.output
    if len(parts) == 1:
        return raw

    # JSON auto-parse
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    if isinstance(parsed, str):
        return parsed

    field_path = parts[1]
    from runsight_core.conditions.engine import resolve_dotted_path

    value = resolve_dotted_path(parsed, field_path)
    if value is None and not (isinstance(parsed, dict) and field_path in parsed):
        raise ValueError(
            f"Input resolution failed: field path '{field_path}' not found in result from '{source_id}'"
        )
    return value


_GATE_INSTRUCTION = (
    "Evaluate the following content and decide if it meets quality standards.\n"
    "Respond with EXACTLY one of:\n"
    "PASS - if the content meets quality standards\n"
    "FAIL: <detailed reason> - if the content needs improvement"
)


def build_block_context(
    block: Any,
    state: WorkflowState,
    step: Optional[Any] = None,
) -> BlockContext:
    """Build a BlockContext for a block from the current workflow state.

    Handles LinearBlock (uses current_task instruction/context) and GateBlock
    (uses gate instruction + resolved eval_key content as context).

    Args:
        block: A block instance with .block_id, .soul, and .runner.
        state: Current WorkflowState with current_task, results, conversation_histories.
        step: Optional Step with declared_inputs to resolve from state.results.

    Returns:
        A fully populated BlockContext ready for block execution.

    Raises:
        ValueError: If state.current_task is None for non-GateBlock, or eval_key missing.
    """
    from runsight_core.memory.token_counting import litellm_token_counter

    # Resolve soul and model
    soul: Optional[Soul] = getattr(block, "soul", None)
    runner = getattr(block, "runner", None)
    model_name: Optional[str] = None
    if soul is not None:
        model_name = soul.model_name
    if not model_name and runner is not None:
        model_name = getattr(runner, "model_name", None)

    # GateBlock strategy: gate instruction + eval_key content as context
    eval_key = getattr(block, "eval_key", None)
    if eval_key is not None:
        if eval_key not in state.results:
            raise ValueError(
                f"build_block_context: GateBlock '{block.block_id}' eval_key '{eval_key}' "
                f"not found in state.results. Available: {sorted(state.results.keys())}"
            )
        raw = state.results[eval_key]
        content = raw.output if isinstance(raw, BlockResult) else str(raw)
        return BlockContext(
            block_id=block.block_id,
            instruction=_GATE_INSTRUCTION,
            context=content,
            inputs={},
            conversation_history=[],
            soul=soul,
            model_name=model_name,
            artifact_store=state.artifact_store,
        )

    # LinearBlock (and others) strategy: use current_task
    if state.current_task is None:
        raise ValueError(
            f"build_block_context: state.current_task is None for block '{block.block_id}'"
        )

    task = state.current_task

    # Resolve declared inputs
    inputs: Dict[str, Any] = {}
    if step is not None and step.declared_inputs:
        for name, from_ref in step.declared_inputs.items():
            inputs[name] = _resolve_ref(from_ref, state)

    # Get conversation history (shallow copy)
    history_key = f"{block.block_id}_{soul.id}" if soul is not None else block.block_id
    history = list(state.conversation_histories.get(history_key, []))

    # Build system_prompt from soul
    system_prompt = soul.system_prompt or "" if soul is not None else ""

    # Call fit_to_budget
    budgeted = fit_to_budget(
        ContextBudgetRequest(
            model=model_name or "",
            system_prompt=system_prompt,
            instruction=task.instruction or "",
            context=task.context or "",
            conversation_history=history,
        ),
        counter=litellm_token_counter,
    )

    return BlockContext(
        block_id=block.block_id,
        instruction=budgeted.task.instruction,
        context=budgeted.task.context,
        inputs=inputs,
        conversation_history=budgeted.messages,
        soul=soul,
        model_name=model_name,
        artifact_store=state.artifact_store,
    )
