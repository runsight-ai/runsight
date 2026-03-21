"""
TeamLeadBlock — analyze failure context and produce recommendations.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner


class TeamLeadBlock(BaseBlock):
    """
    Analyze failure context from shared_memory and produce recommendations.

    Typical Use: After LoopBlock exhausts retries, analyze errors and recommend fixes.
    """

    def __init__(
        self,
        block_id: str,
        failure_context_keys: List[str],
        team_lead_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        super().__init__(block_id)
        if not failure_context_keys:
            raise ValueError(f"TeamLeadBlock {block_id}: failure_context_keys cannot be empty")
        self.failure_context_keys = failure_context_keys
        self.team_lead_soul = team_lead_soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        missing_keys = [key for key in self.failure_context_keys if key not in state.shared_memory]
        if missing_keys:
            raise ValueError(
                f"TeamLeadBlock {self.block_id}: missing failure context keys: {missing_keys}. "
                f"Available keys: {list(state.shared_memory.keys())}"
            )

        error_contexts = []
        for key in self.failure_context_keys:
            context_value = state.shared_memory[key]
            if isinstance(context_value, list):
                formatted = "\n".join([f"  - {item}" for item in context_value])
            else:
                formatted = str(context_value)
            error_contexts.append(f"Context from '{key}':\n{formatted}")

        combined_context = "\n\n".join(error_contexts)

        analysis_instruction = f"""You are analyzing a workflow failure. Review the error context below and provide:
1. Root cause analysis
2. Recommended remediation steps
3. Prevention strategies for future runs

Error Context:
{combined_context}

Provide your analysis and recommendations in a structured format."""

        analysis_task = Task(id=f"{self.block_id}_analysis", instruction=analysis_instruction)

        result = await self.runner.execute_task(analysis_task, self.team_lead_soul)

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=result.output)},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_recommendation": result.output,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] TeamLeadBlock analyzed {len(self.failure_context_keys)} context(s)",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class TeamLeadBlockDef(BaseBlockDef):
    type: Literal["team_lead"] = "team_lead"
    soul_ref: str
    failure_context_keys: Optional[List[str]] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("team_lead", TeamLeadBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> TeamLeadBlock:
    """Build a TeamLeadBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"TeamLeadBlock '{block_id}': soul_ref is required")
    if not block_def.failure_context_keys:
        raise ValueError(
            f"TeamLeadBlock '{block_id}': failure_context_keys is required (non-empty list)"
        )
    soul = resolve_soul(block_def.soul_ref, souls_map)
    return TeamLeadBlock(block_id, block_def.failure_context_keys, soul, runner)


_register_builder("team_lead", build)
