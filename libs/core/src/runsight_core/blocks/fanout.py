"""
FanOutBlock — parallel multi-agent execution.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Literal

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


class FanOutBlock(BaseBlock):
    """
    Executes the current task with multiple agents in parallel.

    Typical Use: Gather diverse perspectives (3 reviewers critique a proposal).
    Output Format: JSON list [{"soul_id": "...", "output": "..."}, ...]
    """

    def __init__(self, block_id: str, souls: List[Soul], runner: RunsightTeamRunner):
        super().__init__(block_id)
        if not souls:
            raise ValueError(f"FanOutBlock {block_id}: souls list cannot be empty")
        self.souls = souls
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if state.current_task is None:
            raise ValueError(f"FanOutBlock {self.block_id}: state.current_task is None")

        task = state.current_task

        if self.stateful:
            histories = {
                soul.id: state.conversation_histories.get(f"{self.block_id}_{soul.id}", [])
                for soul in self.souls
            }

            budgeted_per_soul = {}
            for soul in self.souls:
                model = soul.model_name or self.runner.model_name
                budgeted_per_soul[soul.id] = fit_to_budget(
                    ContextBudgetRequest(
                        model=model,
                        system_prompt=soul.system_prompt or "",
                        instruction=task.instruction or "",
                        context=task.context or "",
                        conversation_history=histories[soul.id],
                    ),
                    counter=litellm_token_counter,
                )

            gather_tasks = [
                self.runner.execute_task(
                    budgeted_per_soul[soul.id].task,
                    soul,
                    messages=budgeted_per_soul[soul.id].messages,
                )
                for soul in self.souls
            ]
            results = await asyncio.gather(*gather_tasks)

            updated_histories = {**state.conversation_histories}
            for soul, result in zip(self.souls, results):
                history_key = f"{self.block_id}_{soul.id}"
                budgeted = budgeted_per_soul[soul.id]
                prompt = self.runner._build_prompt(budgeted.task)
                updated_histories[history_key] = budgeted.messages + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.output},
                ]

            conversation_update = updated_histories
        else:
            gather_tasks = [self.runner.execute_task(task, soul) for soul in self.souls]
            results = await asyncio.gather(*gather_tasks)
            conversation_update = state.conversation_histories

        outputs = [{"soul_id": result.soul_id, "output": result.output} for result in results]

        total_cost = sum(result.cost_usd for result in results)
        total_tokens = sum(result.total_tokens for result in results)

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(outputs, indent=2)),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] FanOut completed with {len(self.souls)} agents",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
                "conversation_histories": conversation_update,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class FanOutBlockDef(BaseBlockDef):
    type: Literal["fanout"] = "fanout"
    soul_refs: List[str]


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("fanout", FanOutBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> FanOutBlock:
    """Build a FanOutBlock from a block definition."""
    if not block_def.soul_refs:
        raise ValueError(f"FanOutBlock '{block_id}': soul_refs is required (non-empty list)")
    souls = [resolve_soul(ref, souls_map) for ref in block_def.soul_refs]
    return FanOutBlock(block_id, souls, runner)


_register_builder("fanout", build)
