"""
RouterBlock — evaluate routing condition using Soul or Callable.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Literal, Optional, Union

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


class RouterBlock(BaseBlock):
    """
    Evaluate routing condition using Soul (LLM) or Callable (function).

    Supports two evaluation modes:
    1. Soul evaluator: LLM decides based on current_task
    2. Callable evaluator: Function evaluates state programmatically

    Typical Use: Decision points in workflows (approve/reject, route selection).
    Output: Decision string stored in results and metadata.
    """

    def __init__(
        self,
        block_id: str,
        condition_evaluator: Union[Soul, Callable[[WorkflowState], str]],
        runner: Optional[RunsightTeamRunner] = None,
    ) -> None:
        super().__init__(block_id)

        if isinstance(condition_evaluator, Soul) and runner is None:
            raise ValueError(
                f"RouterBlock {block_id}: runner is required when condition_evaluator is Soul"
            )

        self.condition_evaluator = condition_evaluator
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        additional_cost = 0.0
        additional_tokens = 0
        if isinstance(self.condition_evaluator, Soul):
            if state.current_task is None:
                raise ValueError(
                    f"RouterBlock {self.block_id}: state.current_task is None (required for Soul evaluator)"
                )
            assert self.runner is not None, "Runner must be provided for Soul evaluator"
            task = state.current_task
            _soul_model = getattr(self.condition_evaluator, "model_name", None)
            _runner_model = getattr(self.runner, "model_name", None)
            model = (
                _soul_model
                if isinstance(_soul_model, str)
                else _runner_model
                if isinstance(_runner_model, str)
                else "gpt-4o-mini"
            )
            budgeted = fit_to_budget(
                ContextBudgetRequest(
                    model=model,
                    system_prompt=getattr(self.condition_evaluator, "system_prompt", "") or "",
                    instruction=task.instruction if isinstance(task.instruction, str) else "",
                    context=task.context if isinstance(task.context, str) else "",
                    conversation_history=[],
                ),
                counter=litellm_token_counter,
            )
            budgeted_context = budgeted.task.context
            fitted_task = (
                task.model_copy(update={"context": budgeted_context}) if budgeted_context else task
            )
            result = await self.runner.execute_task(fitted_task, self.condition_evaluator)
            decision = result.output.strip()
            additional_cost = result.cost_usd
            additional_tokens = result.total_tokens
        else:
            decision = self.condition_evaluator(state)

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=decision, exit_handle=decision),
                },
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_decision": decision,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] RouterBlock decision: {decision}",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + additional_cost,
                "total_tokens": state.total_tokens + additional_tokens,
            }
        )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class RouterBlockDef(BaseBlockDef):
    type: Literal["router"] = "router"
    soul_ref: str
    condition_ref: Optional[str] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("router", RouterBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> RouterBlock:
    """Build a RouterBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(
            f"RouterBlock '{block_id}': soul_ref is required (YAML-based router uses Soul evaluator)"
        )
    soul = resolve_soul(block_def.soul_ref, souls_map)
    return RouterBlock(block_id, soul, runner)


_register_builder("router", build)
