"""
LoopBlock — execute inner blocks for multiple rounds.

Co-located: runtime class + BlockDef schema + CarryContextConfig + build() function.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import convert_condition, convert_condition_group
from runsight_core.state import BlockResult, WorkflowState


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

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        from runsight_core.conditions.engine import (
            ConditionGroup,
            evaluate_condition,
            evaluate_condition_group,
        )

        blocks: Dict[str, BaseBlock] = kwargs.get("blocks", {})
        broke_early = False
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

            for ref in self.inner_block_refs:
                inner_block = blocks.get(ref)
                if inner_block is None:
                    raise ValueError(
                        f"LoopBlock '{self.block_id}': inner block ref '{ref}' "
                        f"not found in blocks dict. "
                        f"Available blocks: {sorted(blocks.keys())}"
                    )
                state = await inner_block.execute(state, **kwargs)

            rounds_completed = round_num

            # Carry context: collect outputs and inject into shared_memory for next round
            if self.carry_context is not None and self.carry_context.enabled:
                source_ids = self.carry_context.source_blocks or self.inner_block_refs
                round_outputs: Dict[str, Any] = {
                    sid: (result.output if hasattr(result, "output") else result)
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

            # Evaluate break condition against the last inner block's output
            if self.break_condition is not None:
                last_ref = self.inner_block_refs[-1]
                _last_result = state.results.get(last_ref)
                last_output = (
                    _last_result.output if hasattr(_last_result, "output") else _last_result
                )
                if isinstance(self.break_condition, ConditionGroup):
                    should_break = evaluate_condition_group(self.break_condition, last_output)
                else:
                    should_break = evaluate_condition(self.break_condition, last_output)
                if should_break:
                    broke_early = True
                    break

        # Store loop metadata in shared_memory
        if broke_early:
            break_reason = "condition met"
        else:
            break_reason = "max_rounds reached"

        meta_key = f"__loop__{self.block_id}"
        state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"completed_{rounds_completed}_rounds"),
                },
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

        return state


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef, ConditionDef, ConditionGroupDef  # noqa: E402


class LoopBlockDef(BaseBlockDef):
    type: Literal["loop"] = "loop"
    inner_block_refs: List[str] = Field(min_length=1)
    max_rounds: int = Field(default=5, ge=1, le=50)
    break_condition: Optional[Union[ConditionDef, ConditionGroupDef]] = None
    carry_context: Optional[CarryContextConfig] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("loop", LoopBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
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
    )


_register_builder("loop", build)
