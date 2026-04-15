"""
LinearBlock — single-agent sequential execution.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


class LinearBlock(BaseBlock):
    """
    Executes a single agent using resolved inputs from upstream blocks.

    Typical Use: Sequential processing where one agent completes a task.
    Example: Research block -> writes research report to results.
    """

    def __init__(self, block_id: str, soul: Soul, runner: RunsightTeamRunner):
        super().__init__(block_id)
        self.soul = soul
        self.runner = runner

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        """Execute block with BlockContext, return BlockOutput."""
        soul = ctx.soul or self.soul

        # ctx.inputs contains declared inputs resolved by build_block_context (RUN-892).
        # When inputs are present, serialize them as the user-turn instruction.
        # When empty, instruction is "" — the soul's system_prompt IS the instruction.
        instruction = json.dumps(ctx.inputs) if ctx.inputs else ""

        if self.stateful:
            history_key = f"{self.block_id}_{soul.id}"
            messages = list(ctx.conversation_history)
            result = await self.runner.execute(instruction, ctx.context, soul, messages=messages)
            new_messages = [
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": result.output},
            ]
            # Use conversation_replacements to store the FULL history as seen by the
            # LLM (pruned ctx.conversation_history + new messages). This ensures the
            # stored history reflects windowing/pruning applied by build_block_context,
            # rather than accumulating unbounded via conversation_updates (append).
            conversation_updates: Optional[Dict[str, Any]] = None
            conversation_replacements: Optional[Dict[str, Any]] = {
                history_key: messages + new_messages
            }
        else:
            result = await self.runner.execute(instruction, ctx.context, soul)
            conversation_updates = None
            conversation_replacements = None

        truncated = result.output[:200] + "..." if len(result.output) > 200 else result.output
        return BlockOutput(
            output=result.output,
            exit_handle=result.exit_handle,
            cost_usd=result.cost_usd,
            total_tokens=result.total_tokens,
            log_entries=[
                {"role": "system", "content": f"[Block {self.block_id}] Completed: {truncated}"}
            ],
            conversation_updates=conversation_updates,
            conversation_replacements=conversation_replacements,
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class LinearBlockDef(BaseBlockDef):
    type: Literal["linear"] = "linear"
    soul_ref: str


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("linear", LinearBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> LinearBlock:
    """Build a LinearBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"LinearBlock '{block_id}': soul_ref is required")
    return LinearBlock(block_id, resolve_soul(block_def.soul_ref, souls_map), runner)


_register_builder("linear", build)
