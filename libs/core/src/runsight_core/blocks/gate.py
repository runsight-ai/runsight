"""
GateBlock — quality gate that evaluates content.

Co-located: runtime class + BlockDef schema + build() function.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner


class GateError(Exception):
    """Structured error raised when a GateBlock evaluation fails.

    Inherits from Exception (not ValueError) to avoid silent swallowing
    by generic ValueError catches. Carries gate_id and the updated
    workflow state so callers (e.g. LoopBlock) can inspect and retry.
    """

    def __init__(self, message: str, *, gate_id: str, state: WorkflowState) -> None:
        super().__init__(message)
        self.gate_id = gate_id
        self.state = state


class GateBlock(BaseBlock):
    """
    Quality gate that evaluates content and either passes or fails the workflow.

    On PASS: stores result (or extracted content) and continues execution.
    On FAIL: raises GateError with structured fields, enabling LoopBlock to catch and retry.
    """

    def __init__(
        self,
        block_id: str,
        gate_soul: Soul,
        eval_key: str,
        runner: RunsightTeamRunner,
        extract_field: Optional[str] = None,
    ):
        super().__init__(block_id)
        self.gate_soul = gate_soul
        self.eval_key = eval_key
        self.runner = runner
        self.extract_field = extract_field

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if self.eval_key not in state.results:
            raise ValueError(
                f"GateBlock '{self.block_id}': eval_key '{self.eval_key}' not found in state.results. "
                f"Available keys: {sorted(state.results.keys())}"
            )

        content = (
            state.results[self.eval_key].output
            if isinstance(state.results[self.eval_key], BlockResult)
            else str(state.results[self.eval_key])
        )

        gate_task = Task(
            id=f"{self.block_id}_eval",
            instruction=(
                "Evaluate the following content and decide if it meets quality standards.\n"
                "Respond with EXACTLY one of:\n"
                "PASS - if the content meets quality standards\n"
                "FAIL: <detailed reason> - if the content needs improvement"
            ),
            context=content,
        )
        model = self.gate_soul.model_name or self.runner.model_name
        budgeted = fit_to_budget(
            ContextBudgetRequest(
                model=model,
                system_prompt=self.gate_soul.system_prompt or "",
                instruction=gate_task.instruction,
                context=gate_task.context or "",
                conversation_history=[],
            ),
            counter=litellm_token_counter,
        )
        result = await self.runner.execute_task(budgeted.task, self.gate_soul)
        decision_line = result.output.strip().split("\n")[0]
        is_pass = decision_line.upper().startswith("PASS")

        if is_pass:
            pass_through = decision_line
            if self.extract_field:
                try:
                    data = json.loads(content)
                    if isinstance(data, list) and data:
                        pass_through = data[-1].get(self.extract_field, decision_line)
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    pass_through = decision_line

            return state.model_copy(
                update={
                    "results": {**state.results, self.block_id: BlockResult(output=pass_through)},
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "pass",
                    },
                    "execution_log": state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": f"[Block {self.block_id}] Gate: PASS",
                        }
                    ],
                    "total_cost_usd": state.total_cost_usd + result.cost_usd,
                    "total_tokens": state.total_tokens + result.total_tokens,
                }
            )
        else:
            feedback = decision_line[5:].strip() if ":" in decision_line else decision_line
            updated_state = state.model_copy(
                update={
                    "total_cost_usd": state.total_cost_usd + result.cost_usd,
                    "total_tokens": state.total_tokens + result.total_tokens,
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "fail",
                    },
                }
            )
            raise GateError(
                f"GateBlock '{self.block_id}' FAILED: {feedback}",
                gate_id=self.block_id,
                state=updated_state,
            )


# -- Schema definition (co-located) -----------------------------------------

from runsight_core.yaml.schema import BaseBlockDef  # noqa: E402


class GateBlockDef(BaseBlockDef):
    type: Literal["gate"] = "gate"
    soul_ref: str
    eval_key: str
    extract_field: Optional[str] = None


# Explicit registration (PEP 563 workaround)
from runsight_core.blocks._registry import register_block_def as _register_block_def  # noqa: E402
from runsight_core.blocks._registry import register_block_builder as _register_builder  # noqa: E402

_register_block_def("gate", GateBlockDef)


# -- Builder function --------------------------------------------------------


def build(
    block_id: str,
    block_def: Any,
    souls_map: Dict[str, Any],
    runner: Any,
    all_blocks: Dict[str, Any],
) -> GateBlock:
    """Build a GateBlock from a block definition."""
    if block_def.soul_ref is None:
        raise ValueError(f"GateBlock '{block_id}': soul_ref is required")
    if block_def.eval_key is None:
        raise ValueError(f"GateBlock '{block_id}': eval_key is required")
    soul = resolve_soul(block_def.soul_ref, souls_map)
    return GateBlock(
        block_id, soul, block_def.eval_key, runner, extract_field=block_def.extract_field
    )


_register_builder("gate", build)
