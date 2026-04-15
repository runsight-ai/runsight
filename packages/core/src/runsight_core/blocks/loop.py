"""
LoopBlock — execute inner blocks for multiple rounds.

Co-located: runtime class + BlockDef schema + CarryContextConfig + build() function.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from runsight_core.blocks._helpers import convert_condition, convert_condition_group
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState

if TYPE_CHECKING:
    from runsight_core.block_io import BlockContext, BlockOutput


class CarryContextConfig(BaseModel):
    """Configuration for carrying context between LoopBlock rounds."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    mode: Literal["last", "all"] = "last"
    source_blocks: Optional[List[str]] = None
    inject_as: str = "previous_round_context"


class LoopBlock(BaseBlock):
    """
    Execute inner blocks sequentially for multiple rounds via flat-ref resolution.

    Typical Use: Writer + critic pattern where multiple blocks iterate in a loop.
    Example: LoopBlock runs [writer, critic] for 3 rounds.
    """

    def __init__(
        self,
        block_id: str,
        inner_block_refs: List[str],
        max_rounds: int = 5,
        break_condition: Optional[Union[Any, Any]] = None,
        carry_context: Optional[CarryContextConfig] = None,
        break_on_exit: Optional[str] = None,
        retry_on_exit: Optional[str] = None,
    ) -> None:
        super().__init__(block_id)
        if not inner_block_refs:
            raise ValueError(f"LoopBlock '{block_id}': inner_block_refs must not be empty")
        if block_id in inner_block_refs:
            raise ValueError(f"LoopBlock '{block_id}': self-reference detected in inner_block_refs")
        if carry_context is not None and carry_context.source_blocks is not None:
            invalid = [sb for sb in carry_context.source_blocks if sb not in inner_block_refs]
            if invalid:
                raise ValueError(
                    f"LoopBlock '{block_id}': carry_context.source_blocks references "
                    f"blocks not in inner_block_refs: {invalid}"
                )
        self.inner_block_refs = inner_block_refs
        self.max_rounds = max_rounds
        self.break_condition = break_condition
        self.carry_context = carry_context
        self.break_on_exit = break_on_exit
        self.retry_on_exit = retry_on_exit

    async def execute(self, ctx: "BlockContext") -> "BlockOutput":
        """New path: run the loop using state_snapshot, return a BlockOutput with diffs."""
        from runsight_core.block_io import BlockOutput

        if ctx.state_snapshot is None:
            raise ValueError(
                f"LoopBlock '{self.block_id}': BlockContext.state_snapshot must not be None"
            )

        blocks: Dict[str, BaseBlock] = ctx.inputs.get("blocks", {})
        bec = ctx.inputs.get("ctx")
        # Capture all parent inputs to forward to inner blocks (preserves kwargs like
        # call_stack, workflow_registry, observer for old-style block compatibility).
        parent_inputs: Dict[str, Any] = dict(ctx.inputs)

        initial_state = ctx.state_snapshot

        (
            final_state,
            broke_early,
            break_reason,
            rounds_completed,
            carry_history,
        ) = await self._run_loop_returning_state(
            initial_state, blocks, bec, parent_inputs=parent_inputs
        )

        # Compute full diff: all keys that are new or changed compared to initial state.
        # This preserves inner block mutations (e.g. custom blocks writing arbitrary keys)
        # while still being a diff (unchanged keys from outer scope are excluded).
        initial_sm = initial_state.shared_memory
        final_sm = final_state.shared_memory
        shared_memory_updates: Dict[str, Any] = {
            k: v for k, v in final_sm.items() if k not in initial_sm or initial_sm[k] != v
        }

        # Exclude keys owned by child LoopBlocks — their round counters, meta keys, and
        # carry_context inject_as keys belong to the child's own BlockOutput, not ours.
        for ref in self.inner_block_refs:
            child = blocks.get(ref)
            if isinstance(child, LoopBlock):
                shared_memory_updates.pop(f"{child.block_id}_round", None)
                shared_memory_updates.pop(f"__loop__{child.block_id}", None)
                if child.carry_context is not None and child.carry_context.enabled:
                    shared_memory_updates.pop(child.carry_context.inject_as, None)

        # Extra results: inner block results that appeared/changed (excluding this loop's own key)
        initial_results = dict(initial_state.results)
        final_results = dict(final_state.results)
        extra_results: Dict[str, Any] = {
            k: v
            for k, v in final_results.items()
            if k != self.block_id and (k not in initial_results or initial_results[k] != v)
        }

        # Conversation history updates: diff between initial and final conversation histories
        initial_conv = dict(initial_state.conversation_histories)
        final_conv = dict(final_state.conversation_histories)
        conversation_updates: Optional[Dict[str, List[Dict]]] = None
        if final_conv != initial_conv:
            conversation_updates = {}
            for key, messages in final_conv.items():
                if key not in initial_conv:
                    conversation_updates[key] = messages
                elif initial_conv[key] != messages:
                    # Only the new messages appended since initial
                    prev_len = len(initial_conv[key])
                    if len(messages) > prev_len:
                        conversation_updates[key] = messages[prev_len:]

        cost_usd = final_state.total_cost_usd - initial_state.total_cost_usd
        total_tokens = final_state.total_tokens - initial_state.total_tokens

        log_entries = [
            {
                "block_id": self.block_id,
                "event": "loop_complete",
                "rounds_completed": str(rounds_completed),
                "broke_early": str(broke_early),
            }
        ]

        # Propagate current_task.context changes (e.g. carry_context updates).
        current_task_context: Optional[str] = None
        if (
            final_state.current_task is not None
            and initial_state.current_task is not None
            and final_state.current_task.context != initial_state.current_task.context
        ):
            current_task_context = final_state.current_task.context

        return BlockOutput(
            output=f"completed_{rounds_completed}_rounds",
            cost_usd=cost_usd,
            total_tokens=total_tokens,
            shared_memory_updates=shared_memory_updates,
            extra_results=extra_results if extra_results else None,
            conversation_updates=conversation_updates,
            log_entries=log_entries,
            current_task_context=current_task_context,
        )

    async def _run_loop_returning_state(
        self,
        state: WorkflowState,
        blocks: Dict[str, BaseBlock],
        ctx: Any,
        parent_inputs: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Run the loop logic and return (final_state, broke_early, break_reason, rounds_completed, carry_history)."""
        from runsight_core.conditions.engine import (
            ConditionGroup,
            evaluate_condition,
            evaluate_condition_group,
        )

        broke_early = False
        break_reason: Optional[str] = None
        rounds_completed = 0
        carry_history: List[Dict[str, Any]] = []

        for round_num in range(1, self.max_rounds + 1):
            state = state.model_copy(
                update={
                    "shared_memory": {
                        **state.shared_memory,
                        f"{self.block_id}_round": round_num,
                    },
                }
            )

            should_retry = False
            for ref in self.inner_block_refs:
                inner_block = blocks.get(ref)
                if inner_block is None:
                    raise ValueError(
                        f"LoopBlock '{self.block_id}': inner block ref '{ref}' "
                        f"not found in blocks dict. "
                        f"Available blocks: {sorted(blocks.keys())}"
                    )
                # Use module-level execute_block so tests can patch it.
                # Pass parent_inputs as extra_inputs only when there's no
                # BlockExecutionContext — in that case workflow.execute_block handles
                # the full dispatch and extra_inputs is not needed.
                from runsight_core.workflow import BlockExecutionContext as _BEC

                if not isinstance(ctx, _BEC) and parent_inputs:
                    state = await execute_block(inner_block, state, ctx, extra_inputs=parent_inputs)
                else:
                    state = await execute_block(inner_block, state, ctx)

                # Check exit_handle after each inner block
                result = state.results.get(ref)
                if isinstance(result, BlockResult) and result.exit_handle is not None:
                    if self.break_on_exit and result.exit_handle == self.break_on_exit:
                        broke_early = True
                        break_reason = f"exit_handle '{result.exit_handle}' matched break_on_exit"
                        break
                    if self.retry_on_exit and result.exit_handle == self.retry_on_exit:
                        should_retry = True
                        break

            rounds_completed = round_num

            if self.carry_context is not None and self.carry_context.enabled:
                source_ids = self.carry_context.source_blocks or self.inner_block_refs
                round_outputs: Dict[str, Any] = {
                    sid: (result.output if isinstance(result, BlockResult) else result)
                    if (result := state.results.get(sid)) is not None
                    else None
                    for sid in source_ids
                }
                carry_history.append(round_outputs)

                if self.carry_context.mode == "last":
                    inject_value: Any = round_outputs
                else:  # mode == "all"
                    inject_value = list(carry_history)

                state = state.model_copy(
                    update={
                        "shared_memory": {
                            **state.shared_memory,
                            self.carry_context.inject_as: inject_value,
                        },
                    }
                )

                if state.current_task is not None:
                    if isinstance(inject_value, list):
                        parts = []
                        for idx, entry in enumerate(inject_value):
                            parts.append(f"=== round_{idx + 1} ===")
                            parts.append(json.dumps(entry, default=str))
                        carry_context_str = "\n".join(parts)
                    else:
                        carry_context_str = json.dumps(inject_value, default=str)

                    from runsight_core.memory.budget import (  # noqa: PLC0415
                        ContextBudgetRequest,
                    )
                    from runsight_core.memory.budget import (
                        fit_to_budget as _fit,
                    )
                    from runsight_core.memory.token_counting import (
                        litellm_token_counter,  # noqa: PLC0415
                    )

                    _inner_model = "gpt-4o-mini"
                    for ref in self.inner_block_refs:
                        _ib = blocks.get(ref)
                        if _ib:
                            _soul = getattr(_ib, "soul", None)
                            if _soul is not None:
                                _inner_model = _soul.model_name or (
                                    _ib.runner.model_name
                                    if hasattr(_ib, "runner")
                                    else _inner_model
                                )
                                break

                    _budgeted = _fit(
                        ContextBudgetRequest(
                            model=_inner_model,
                            system_prompt="",
                            instruction="",
                            context=carry_context_str,
                            conversation_history=[],
                            budget_ratio=0.03,
                            output_token_reserve=0,
                        ),
                        counter=litellm_token_counter,
                    )
                    task_context = _budgeted.task.context or carry_context_str

                    state = state.model_copy(
                        update={
                            "current_task": state.current_task.model_copy(
                                update={"context": task_context}
                            ),
                        }
                    )

            if broke_early:
                break

            if should_retry:
                continue

            if self.break_condition is not None:
                last_ref = self.inner_block_refs[-1]
                _last_result = state.results.get(last_ref)
                last_output = (
                    _last_result.output if isinstance(_last_result, BlockResult) else _last_result
                )
                if isinstance(self.break_condition, ConditionGroup):
                    should_break = evaluate_condition_group(self.break_condition, last_output)
                else:
                    should_break = evaluate_condition(self.break_condition, last_output)
                if should_break:
                    broke_early = True
                    break

        if broke_early and break_reason is None:
            break_reason = "condition met"
        elif not broke_early:
            break_reason = "max_rounds reached"

        meta_key = f"__loop__{self.block_id}"
        state = state.model_copy(
            update={
                "shared_memory": {
                    **state.shared_memory,
                    meta_key: {
                        "rounds_completed": rounds_completed,
                        "broke_early": broke_early,
                        "break_reason": break_reason,
                    },
                },
            }
        )

        return state, broke_early, break_reason, rounds_completed, carry_history


async def execute_block(
    block: BaseBlock,
    state: WorkflowState,
    ctx: Any,
    extra_inputs: Optional[Dict[str, Any]] = None,
) -> WorkflowState:
    """Inner-block dispatcher used by LoopBlock._run_loop_returning_state.

    When ctx is a BlockExecutionContext, delegates to workflow.execute_block for all
    block types so that observer events, retry config, block-level budget session,
    timeout, and exit condition evaluation are all applied.

    When ctx is None, builds a minimal BlockContext and dispatches directly.
    extra_inputs are merged into the BlockContext.inputs so that old-style blocks
    receiving kwargs (e.g. blocks, call_stack, observer) continue to work.

    This function is intentionally module-level so that tests can patch it via
    ``patch("runsight_core.blocks.loop.execute_block", ...)``.
    """
    from runsight_core.block_io import apply_block_output, build_block_context
    from runsight_core.workflow import BlockExecutionContext
    from runsight_core.workflow import execute_block as workflow_execute_block

    if isinstance(ctx, BlockExecutionContext):
        return await workflow_execute_block(block, state, ctx)

    # ctx is None: build a BlockContext and dispatch directly
    block_ctx = build_block_context(block, state)
    if extra_inputs:
        block_ctx = block_ctx.model_copy(update={"inputs": {**block_ctx.inputs, **extra_inputs}})
    output = await block.execute(block_ctx)
    # Backward compat: old-style blocks may return WorkflowState directly.
    if isinstance(output, WorkflowState):
        return output
    return apply_block_output(state, block.block_id, output)


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef, ConditionDef, ConditionGroupDef  # noqa: E402


class LoopBlockDef(BaseBlockDef):
    type: Literal["loop"] = "loop"
    inner_block_refs: List[str] = Field(min_length=1)
    max_rounds: int = Field(default=5, ge=1, le=50)
    break_condition: Optional[Union[ConditionDef, ConditionGroupDef]] = None
    carry_context: Optional[CarryContextConfig] = None
    break_on_exit: Optional[str] = None
    retry_on_exit: Optional[str] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("loop", LoopBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> LoopBlock:
    """Build a LoopBlock from a block definition."""
    break_condition = None
    if block_def.break_condition is not None:
        if isinstance(block_def.break_condition, ConditionGroupDef):
            break_condition = convert_condition_group(block_def.break_condition)
        else:
            break_condition = convert_condition(block_def.break_condition)
    return LoopBlock(
        block_id=block_id,
        inner_block_refs=list(block_def.inner_block_refs),
        max_rounds=block_def.max_rounds,
        break_condition=break_condition,
        carry_context=block_def.carry_context,
        break_on_exit=block_def.break_on_exit,
        retry_on_exit=block_def.retry_on_exit,
    )


_register_builder("loop", build)
