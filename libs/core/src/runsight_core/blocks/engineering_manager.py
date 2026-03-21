"""
EngineeringManagerBlock — generate alternative execution plans.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner


class EngineeringManagerBlock(BaseBlock):
    """
    Generate alternative execution plan using LLM, parse into structured steps.

    Typical Use: After workflow failure, generate new plan with structured steps.
    """

    def __init__(
        self,
        block_id: str,
        engineering_manager_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        super().__init__(block_id)
        self.engineering_manager_soul = engineering_manager_soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if state.current_task is None:
            raise ValueError(f"EngineeringManagerBlock {self.block_id}: state.current_task is None")

        context_parts = [f"Original Goal: {state.current_task.instruction}"]

        if f"{self.block_id}_previous_errors" in state.shared_memory:
            context_parts.append(
                f"Previous Errors:\n{state.shared_memory[f'{self.block_id}_previous_errors']}"
            )

        combined_context = "\n\n".join(context_parts)

        planning_instruction = f"""You are a workflow planner. Given the context below, create a detailed execution plan.

{combined_context}

Provide your plan as a numbered list where each step follows this format:
<step_number>. <step_id>: <description>

Example:
1. research_phase: Gather requirements and analyze constraints
2. design_phase: Create technical architecture
3. implementation_phase: Implement core features

Your plan:"""

        planning_task = Task(id=f"{self.block_id}_planning", instruction=planning_instruction)

        result = await self.runner.execute_task(planning_task, self.engineering_manager_soul)
        text_plan = result.output

        step_pattern = re.compile(r"^\d+\.\s+([^:]+):\s+(.+)$", re.MULTILINE)
        matches = step_pattern.findall(text_plan)

        structured_steps: List[Dict[str, str]] = []
        if matches:
            for step_id, description in matches:
                structured_steps.append(
                    {"step_id": step_id.strip(), "description": description.strip()}
                )
        else:
            structured_steps = [
                {
                    "step_id": "replanned_execution",
                    "description": text_plan[:200] + "..." if len(text_plan) > 200 else text_plan,
                }
            ]

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=text_plan)},
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_new_steps": structured_steps,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] EngineeringManagerBlock generated {len(structured_steps)} step(s)",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class EngineeringManagerBlockDef(BaseBlockDef):
    type: Literal["engineering_manager"] = "engineering_manager"
    soul_ref: str


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("engineering_manager", EngineeringManagerBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> EngineeringManagerBlock:
    """Build an EngineeringManagerBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"EngineeringManagerBlock '{block_id}': soul_ref is required")
    soul = resolve_soul(block_def.soul_ref, souls_map)
    return EngineeringManagerBlock(block_id, soul, runner)


_register_builder("engineering_manager", build)
