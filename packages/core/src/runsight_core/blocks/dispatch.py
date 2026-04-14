"""
DispatchBlock — parallel multi-agent execution with per-exit tasks.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Union

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState


@dataclass
class DispatchBranch:
    """A single branch (exit) in a DispatchBlock with its own soul and task instruction."""

    exit_id: str
    label: str
    soul: Soul
    task_instruction: str


class DispatchBlock(BaseBlock):
    """
    Executes per-branch tasks with different agents in parallel.

    Each branch has its own exit_id, soul, and task_instruction. Results are keyed
    per-exit at state.results["{block_id}.{exit_id}"] and combined at state.results["{block_id}"].
    """

    def __init__(self, block_id: str, branches: List[DispatchBranch], runner: RunsightTeamRunner):
        super().__init__(block_id)
        if not branches:
            raise ValueError(f"DispatchBlock {block_id}: branches list cannot be empty")
        self.branches = branches
        self.runner = runner

    async def _gather_with_budget_isolation(self, coros: List[tuple[str, Any]]) -> List[Any]:
        """Run branch coroutines via asyncio.gather with budget session isolation.

        When a parent BudgetSession is active, each branch gets an isolated child
        session via copy_context() so concurrent branches don't share mutable state.
        After gather, child costs are reconciled to parent and flow-level caps checked.
        When no budget is set, runs exactly as plain asyncio.gather().
        """
        parent_session: BudgetSession | None = _active_budget.get(None)

        if parent_session is None:
            return list(await asyncio.gather(*(coro for _, coro in coros)))

        children: List[BudgetSession] = []
        loop = asyncio.get_running_loop()
        gathered_tasks = []

        for exit_id, coro in coros:
            child = parent_session.create_isolated_child(branch_id=exit_id)
            children.append(child)

            ctx = contextvars.copy_context()
            ctx.run(_active_budget.set, child)

            gathered_tasks.append(loop.create_task(coro, context=ctx))

        results = list(await asyncio.gather(*gathered_tasks))

        for child in children:
            parent_session.reconcile_child(child)

        parent_session.check_or_raise()

        return results

    async def execute(  # type: ignore[override]
        self,
        state_or_ctx: Union[BlockContext, WorkflowState],
        **kwargs: Any,
    ) -> Union[BlockOutput, WorkflowState]:
        """Execute block. Accepts BlockContext (new path) or WorkflowState (legacy path)."""
        if isinstance(state_or_ctx, BlockContext):
            return await self._execute_with_context(state_or_ctx)
        return await self._execute_with_state(state_or_ctx, **kwargs)

    @staticmethod
    async def _accrue_and_return(coro: Any) -> Any:
        """Wrap a branch coroutine to accrue its cost into the active budget session."""
        result = await coro
        session = _active_budget.get(None)
        if session is not None:
            session.accrue(cost_usd=result.cost_usd, tokens=result.total_tokens)
        return result

    async def _execute_with_context(self, ctx: BlockContext) -> BlockOutput:
        """New path: accept BlockContext, return pure BlockOutput (no state mutation)."""
        context = ctx.context

        if self.stateful:
            histories = {
                branch.exit_id: list(
                    ctx.conversation_history
                    if ctx.conversation_history
                    else ctx.inputs.get(f"{self.block_id}_{branch.exit_id}", [])
                )
                for branch in self.branches
            }

            budgeted_per_branch = {}
            for branch in self.branches:
                model = branch.soul.model_name or self.runner.model_name
                budgeted_per_branch[branch.exit_id] = fit_to_budget(
                    ContextBudgetRequest(
                        model=model,
                        system_prompt=branch.soul.system_prompt or "",
                        instruction=branch.task_instruction,
                        context=context or "",
                        conversation_history=histories[branch.exit_id],
                    ),
                    counter=litellm_token_counter,
                )

            gather_coros = []
            for branch in self.branches:
                budgeted = budgeted_per_branch[branch.exit_id]
                task = Task(
                    id=f"{self.block_id}_{branch.exit_id}",
                    instruction=budgeted.task.instruction,
                    context=budgeted.task.context,
                )
                gather_coros.append(
                    (
                        branch.exit_id,
                        self._accrue_and_return(
                            self.runner.execute_task(task, branch.soul, messages=budgeted.messages)
                        ),
                    )
                )
            results = await self._gather_with_budget_isolation(gather_coros)

            conversation_updates: Dict[str, List[Dict]] = {}
            for branch, result in zip(self.branches, results):
                history_key = f"{self.block_id}_{branch.exit_id}"
                budgeted = budgeted_per_branch[branch.exit_id]
                prompt = self.runner._build_prompt(budgeted.task)
                conversation_updates[history_key] = budgeted.messages + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.output},
                ]
        else:
            gather_coros = [
                (
                    branch.exit_id,
                    self._accrue_and_return(
                        self.runner.execute_task(
                            Task(
                                id=f"{self.block_id}_{branch.exit_id}",
                                instruction=branch.task_instruction,
                                context=context,
                            ),
                            branch.soul,
                        )
                    ),
                )
                for branch in self.branches
            ]
            results = await self._gather_with_budget_isolation(gather_coros)
            conversation_updates = None  # type: ignore[assignment]

        # Build per-exit results and combined output
        extra_results: Dict[str, Any] = {}
        combined_list = []
        for branch, result in zip(self.branches, results):
            extra_results[f"{self.block_id}.{branch.exit_id}"] = BlockResult(
                output=result.output,
                exit_handle=branch.exit_id,
            )
            combined_list.append({"exit_id": branch.exit_id, "output": result.output})

        total_cost = sum(r.cost_usd for r in results)
        total_tokens = sum(r.total_tokens for r in results)

        return BlockOutput(
            output=json.dumps(combined_list),
            cost_usd=total_cost,
            total_tokens=total_tokens,
            log_entries=[
                {
                    "role": "system",
                    "content": (
                        f"[Block {self.block_id}] Dispatch completed"
                        f" with {len(self.branches)} branches"
                    ),
                }
            ],
            extra_results=extra_results,
            conversation_updates=conversation_updates if self.stateful else None,
        )

    async def _execute_with_state(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        """Legacy path: accept WorkflowState, return updated WorkflowState."""
        context = state.current_task.context if state.current_task is not None else None

        if self.stateful:
            histories = {
                branch.exit_id: state.conversation_histories.get(
                    f"{self.block_id}_{branch.exit_id}", []
                )
                for branch in self.branches
            }

            budgeted_per_branch = {}
            for branch in self.branches:
                model = branch.soul.model_name or self.runner.model_name
                budgeted_per_branch[branch.exit_id] = fit_to_budget(
                    ContextBudgetRequest(
                        model=model,
                        system_prompt=branch.soul.system_prompt or "",
                        instruction=branch.task_instruction,
                        context=context or "",
                        conversation_history=histories[branch.exit_id],
                    ),
                    counter=litellm_token_counter,
                )

            gather_coros = []
            for branch in self.branches:
                budgeted = budgeted_per_branch[branch.exit_id]
                task = Task(
                    id=f"{self.block_id}_{branch.exit_id}",
                    instruction=budgeted.task.instruction,
                    context=budgeted.task.context,
                )
                gather_coros.append(
                    (
                        branch.exit_id,
                        self.runner.execute_task(
                            task,
                            branch.soul,
                            messages=budgeted.messages,
                        ),
                    )
                )
            results = await self._gather_with_budget_isolation(gather_coros)

            updated_histories = {**state.conversation_histories}
            for branch, result in zip(self.branches, results):
                history_key = f"{self.block_id}_{branch.exit_id}"
                budgeted = budgeted_per_branch[branch.exit_id]
                prompt = self.runner._build_prompt(budgeted.task)
                updated_histories[history_key] = budgeted.messages + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.output},
                ]

            conversation_update = updated_histories
        else:
            gather_coros = [
                (
                    branch.exit_id,
                    self.runner.execute_task(
                        Task(
                            id=f"{self.block_id}_{branch.exit_id}",
                            instruction=branch.task_instruction,
                            context=context,
                        ),
                        branch.soul,
                    ),
                )
                for branch in self.branches
            ]
            results = await self._gather_with_budget_isolation(gather_coros)
            conversation_update = state.conversation_histories

        # Per-exit results and combined output
        per_exit_results = {}
        combined_list = []
        for branch, result in zip(self.branches, results):
            per_exit_results[f"{self.block_id}.{branch.exit_id}"] = BlockResult(
                output=result.output,
                exit_handle=branch.exit_id,
            )
            combined_list.append({"exit_id": branch.exit_id, "output": result.output})

        total_cost = sum(result.cost_usd for result in results)
        total_tokens = sum(result.total_tokens for result in results)

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    **per_exit_results,
                    self.block_id: BlockResult(output=json.dumps(combined_list)),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": (
                            f"[Block {self.block_id}] Dispatch completed"
                            f" with {len(self.branches)} branches"
                        ),
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
                "conversation_histories": conversation_update,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef, DispatchExitDef  # noqa: E402


class DispatchBlockDef(BaseBlockDef):
    type: Literal["dispatch"] = "dispatch"
    exits: List[DispatchExitDef]


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402

_register_block_def("dispatch", DispatchBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
    **_: Any,
) -> DispatchBlock:
    """Build a DispatchBlock from a block definition."""
    if not block_def.exits:
        raise ValueError(f"DispatchBlock '{block_id}': exits list cannot be empty")
    branches = [
        DispatchBranch(
            exit_id=exit_def.id,
            label=exit_def.label,
            soul=resolve_soul(exit_def.soul_ref, souls_map),
            task_instruction=exit_def.task,
        )
        for exit_def in block_def.exits
    ]
    return DispatchBlock(block_id, branches, runner)


_register_builder("dispatch", build)
