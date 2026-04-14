"""
LinearBlock — single-agent sequential execution.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState


class LinearBlock(BaseBlock):
    """
    Executes the current task with a single agent.

    Typical Use: Sequential processing where one agent completes a task.
    Example: Research block -> writes research report to results.
    """

    def __init__(self, block_id: str, soul: Soul, runner: RunsightTeamRunner):
        super().__init__(block_id)
        self.soul = soul
        self.runner = runner

    async def execute(  # type: ignore[override]
        self,
        state_or_ctx: Union[BlockContext, WorkflowState],
        **kwargs: Any,
    ) -> Union[BlockOutput, WorkflowState]:
        """Execute block. Accepts BlockContext (new path) or WorkflowState (legacy path)."""
        if isinstance(state_or_ctx, BlockContext):
            return await self._execute_with_context(state_or_ctx)
        return await self._execute_with_state(state_or_ctx, **kwargs)

    async def _execute_with_context(self, ctx: BlockContext) -> BlockOutput:
        """New path: accept BlockContext, return pure BlockOutput (no state mutation)."""
        soul = ctx.soul or self.soul

        if self.stateful:
            history_key = f"{self.block_id}_{soul.id}"
            messages = list(ctx.conversation_history)
            task = Task(
                id=f"{self.block_id}_task",
                instruction=ctx.instruction,
                context=ctx.context or "",
            )
            result = await self.runner.execute_task(task, soul, messages=messages)
            prompt = self.runner._build_prompt(task)
            new_messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": result.output},
            ]
            conversation_updates: Optional[Dict[str, Any]] = {history_key: new_messages}
        else:
            task = Task(
                id=f"{self.block_id}_task",
                instruction=ctx.instruction,
                context=ctx.context or "",
            )
            result = await self.runner.execute_task(task, soul)
            conversation_updates = None

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
        )

    async def _execute_with_state(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        """Legacy path: accept WorkflowState, return updated WorkflowState."""
        if state.current_task is None:
            raise ValueError(f"LinearBlock {self.block_id}: state.current_task is None")

        task = state.current_task

        if self.stateful:
            model = self.soul.model_name or self.runner.model_name
            history_key = f"{self.block_id}_{self.soul.id}"
            history = state.conversation_histories.get(history_key, [])
            budgeted = fit_to_budget(
                ContextBudgetRequest(
                    model=model,
                    system_prompt=self.soul.system_prompt or "",
                    instruction=task.instruction or "",
                    context=task.context or "",
                    conversation_history=history,
                ),
                counter=litellm_token_counter,
            )
            result = await self.runner.execute_task(
                budgeted.task, self.soul, messages=budgeted.messages
            )
            prompt = self.runner._build_prompt(budgeted.task)
            updated_history = budgeted.messages + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": result.output},
            ]
            conversation_update = {**state.conversation_histories, history_key: updated_history}
        else:
            result = await self.runner.execute_task(task, self.soul)
            conversation_update = state.conversation_histories

        truncated = result.output[:200] + "..." if len(result.output) > 200 else result.output

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=result.output,
                        exit_handle=result.exit_handle,
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {"role": "system", "content": f"[Block {self.block_id}] Completed: {truncated}"}
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
                "conversation_histories": conversation_update,
            }
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
