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
    conversation_replacements: Optional[Dict[str, List[Dict]]] = None
    shared_memory_updates: Optional[Dict[str, Any]] = None
    extra_results: Optional[Dict[str, Any]] = None
    metadata_updates: Optional[Dict[str, Any]] = None
    current_task_context: Optional[str] = None


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
    if output.conversation_replacements is not None:
        # Replaces (overwrites) histories rather than appending.
        # Used by DispatchBlock stateful mode to store full pruned+new history.
        for key, messages in output.conversation_replacements.items():
            new_conversation_histories[key] = list(messages)

    new_metadata = dict(state.metadata)
    if output.metadata_updates is not None:
        new_metadata.update(output.metadata_updates)

    state_updates: Dict[str, Any] = {
        "results": new_results,
        "total_cost_usd": state.total_cost_usd + output.cost_usd,
        "total_tokens": state.total_tokens + output.total_tokens,
        "execution_log": new_execution_log,
        "shared_memory": new_shared_memory,
        "conversation_histories": new_conversation_histories,
        "metadata": new_metadata,
    }
    # Propagate carry_context from loop blocks into shared_memory _resolved_inputs.
    if output.current_task_context is not None:
        existing_resolved = dict(new_shared_memory.get("_resolved_inputs", {}))
        existing_resolved["context"] = output.current_task_context
        new_shared_memory["_resolved_inputs"] = existing_resolved
        state_updates["shared_memory"] = new_shared_memory

    return state.model_copy(update=state_updates)


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

    Instruction and context are sourced from:
    - state.shared_memory["_resolved_inputs"] (populated by the Step wrapper)
    - The block soul's system_prompt (for LinearBlock instruction)
    - state.results["workflow"] (virtual block result seeded by the API for external input)
    - Block-type-specific logic (GateBlock, DispatchBlock, SynthesizeBlock, etc.)

    Args:
        block: A block instance with .block_id, .soul, and .runner.
        state: Current WorkflowState with results, conversation_histories, shared_memory.
        step: Optional Step with declared_inputs to resolve from state.results.

    Returns:
        A fully populated BlockContext ready for block execution.

    Raises:
        ValueError: If a required input (eval_key for GateBlock, etc.) is missing.
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

    # WorkflowBlock strategy: detect child_workflow attribute
    child_workflow = getattr(block, "child_workflow", None)
    if child_workflow is not None:
        return BlockContext(
            block_id=block.block_id,
            instruction="invoke child",
            context=None,
            inputs={
                "call_stack": [],
                "workflow_registry": None,
                "observer": None,
            },
            conversation_history=[],
            soul=None,
            model_name=None,
            state_snapshot=state,
        )

    # LoopBlock strategy: detect inner_block_refs attribute
    inner_block_refs = getattr(block, "inner_block_refs", None)
    if inner_block_refs is not None:
        return BlockContext(
            block_id=block.block_id,
            instruction="loop",
            context=None,
            inputs={},
            conversation_history=[],
            soul=None,
            model_name=None,
            state_snapshot=state,
        )

    # CodeBlock strategy: detect code attribute (no LLM, "access: all" pattern)
    code = getattr(block, "code", None)
    if code is not None:
        return BlockContext(
            block_id=block.block_id,
            instruction="",
            context=None,
            inputs={
                "results": {
                    k: v.output if isinstance(v, BlockResult) else v
                    for k, v in state.results.items()
                },
                "metadata": state.metadata,
                "shared_memory": state.shared_memory,
            },
            conversation_history=[],
            soul=None,
            model_name=None,
            state_snapshot=state,
        )

    # DispatchBlock strategy: detect branches attribute
    branches = getattr(block, "branches", None)
    if branches is not None:
        first_branch = branches[0] if branches else None
        dispatch_soul: Optional[Soul] = first_branch.soul if first_branch is not None else soul
        dispatch_instruction = (
            first_branch.task_instruction
            if first_branch is not None and getattr(first_branch, "task_instruction", None)
            else "dispatch"
        )
        resolved_inputs = state.shared_memory.get("_resolved_inputs", {})
        dispatch_context = resolved_inputs.get("context") if resolved_inputs else None
        return BlockContext(
            block_id=block.block_id,
            instruction=dispatch_instruction,
            context=dispatch_context,
            inputs={},
            conversation_history=[],
            soul=dispatch_soul,
            model_name=model_name,
            artifact_store=getattr(state, "artifact_store", None),
            state_snapshot=state,
        )

    # SynthesizeBlock strategy: detect input_block_ids attribute
    input_block_ids = getattr(block, "input_block_ids", None)
    if input_block_ids is not None:
        missing = [bid for bid in input_block_ids if bid not in state.results]
        if missing:
            available = sorted(state.results.keys())
            raise ValueError(
                f"build_block_context: SynthesizeBlock '{block.block_id}' missing inputs: {missing}. "
                f"Available: {available}"
            )
        combined_outputs = "\n\n".join(
            f"=== Output from {bid} ===\n"
            + (
                state.results[bid].output
                if isinstance(state.results[bid], BlockResult)
                else str(state.results[bid])
            )
            for bid in input_block_ids
        )
        synthesis_instruction = (
            "Synthesize the following outputs into a cohesive, unified result. "
            "Identify common themes, resolve conflicts, and provide a comprehensive summary."
        )
        synth_soul: Optional[Soul] = getattr(block, "synthesizer_soul", soul)
        return BlockContext(
            block_id=block.block_id,
            instruction=synthesis_instruction,
            context=combined_outputs,
            inputs={},
            conversation_history=[],
            soul=synth_soul,
            model_name=model_name,
            artifact_store=getattr(state, "artifact_store", None),
            state_snapshot=state,
        )

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
            state_snapshot=state,
        )

    # Resolve declared inputs (done here so it applies even when current_task is None).
    inputs: Dict[str, Any] = {}
    if step is not None and step.declared_inputs:
        for name, from_ref in step.declared_inputs.items():
            inputs[name] = _resolve_ref(from_ref, state)

    # LinearBlock (and others) strategy: build from _resolved_inputs and soul system_prompt
    resolved_inputs = state.shared_memory.get("_resolved_inputs", {})

    # Instruction: prefer soul system_prompt, fall back to _resolved_inputs["instruction"], then ""
    system_prompt = soul.system_prompt or "" if soul is not None else ""
    instruction = system_prompt or resolved_inputs.get("instruction", "") or ""

    # Context: workflow-level external input or resolved context input
    workflow_result = state.results.get("workflow")
    if workflow_result is not None:
        raw_context = (
            workflow_result.output
            if isinstance(workflow_result, BlockResult)
            else str(workflow_result)
        )
    else:
        raw_context = resolved_inputs.get("context", "") or ""

    # Get conversation history (shallow copy)
    history_key = f"{block.block_id}_{soul.id}" if soul is not None else block.block_id
    history = list(state.conversation_histories.get(history_key, []))

    # Call fit_to_budget — use a safe default model when none is configured.
    # Guard against non-string model_name (e.g. MagicMock in tests).
    _model = model_name if isinstance(model_name, str) else "gpt-4o-mini"
    budgeted = fit_to_budget(
        ContextBudgetRequest(
            model=_model,
            system_prompt=system_prompt,
            instruction=instruction,
            context=raw_context,
            conversation_history=history,
        ),
        counter=litellm_token_counter,
    )

    return BlockContext(
        block_id=block.block_id,
        instruction=budgeted.instruction,
        context=budgeted.context,
        inputs=inputs,
        conversation_history=budgeted.messages,
        soul=soul,
        model_name=model_name if isinstance(model_name, str) else None,
        artifact_store=state.artifact_store,
        state_snapshot=state,
    )
