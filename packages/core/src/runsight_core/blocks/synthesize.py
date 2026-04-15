"""
SynthesizeBlock — combine outputs from multiple blocks.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


class SynthesizeBlock(BaseBlock):
    """
    Reads outputs from multiple input blocks and synthesizes them into a cohesive result.

    Typical Use: Combine research + code + review into final report.
    """

    def __init__(
        self,
        block_id: str,
        input_block_ids: List[str],
        synthesizer_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        super().__init__(block_id)
        if not input_block_ids:
            raise ValueError(f"SynthesizeBlock {block_id}: input_block_ids cannot be empty")
        self.input_block_ids = input_block_ids
        self.synthesizer_soul = synthesizer_soul
        self.soul = synthesizer_soul
        self.runner = runner

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        """Execute block with BlockContext, return BlockOutput."""
        soul = ctx.soul or self.synthesizer_soul
        result = await self.runner.execute(ctx.instruction, ctx.context, soul)
        return BlockOutput(
            output=result.output,
            cost_usd=result.cost_usd,
            total_tokens=result.total_tokens,
            log_entries=[
                {
                    "role": "system",
                    "content": f"[Block {self.block_id}] Synthesized {len(self.input_block_ids)} inputs",
                }
            ],
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class SynthesizeBlockDef(BaseBlockDef):
    type: Literal["synthesize"] = "synthesize"
    soul_ref: str
    input_block_ids: List[str]


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("synthesize", SynthesizeBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> SynthesizeBlock:
    """Build a SynthesizeBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"SynthesizeBlock '{block_id}': soul_ref is required")
    if not block_def.input_block_ids:
        raise ValueError(
            f"SynthesizeBlock '{block_id}': input_block_ids is required (non-empty list)"
        )
    soul = resolve_soul(block_def.soul_ref, souls_map)
    return SynthesizeBlock(block_id, block_def.input_block_ids, soul, runner)


_register_builder("synthesize", build)
