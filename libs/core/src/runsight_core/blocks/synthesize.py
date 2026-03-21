"""
SynthesizeBlock — combine outputs from multiple blocks.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
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
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        missing = [bid for bid in self.input_block_ids if bid not in state.results]
        if missing:
            raise ValueError(
                f"SynthesizeBlock {self.block_id}: missing inputs: {missing}. "
                f"Available: {list(state.results.keys())}"
            )

        combined_outputs = "\n\n".join(
            [
                f"=== Output from {bid} ===\n{state.results[bid].output if hasattr(state.results[bid], 'output') else state.results[bid]}"
                for bid in self.input_block_ids
            ]
        )

        synthesis_instruction = (
            "Synthesize the following outputs into a cohesive, unified result. "
            "Identify common themes, resolve conflicts, and provide a comprehensive summary.\n\n"
            f"{combined_outputs}"
        )
        synthesis_task = Task(id=f"{self.block_id}_synthesis", instruction=synthesis_instruction)

        result = await self.runner.execute_task(synthesis_task, self.synthesizer_soul)

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=result.output)},
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Synthesized {len(self.input_block_ids)} inputs",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class SynthesizeBlockDef(BaseBlockDef):
    type: Literal["synthesize"] = "synthesize"
    soul_ref: str
    input_block_ids: List[str]


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("synthesize", SynthesizeBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
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
