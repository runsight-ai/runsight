"""Package-local DispatchBlock test builders."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import BlockExecutionContext


@pytest.fixture
def mock_runner():
    return make_mock_runner()


def make_mock_runner(model_name: str = "dispatch-fixture-model"):
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = model_name
    runner._build_prompt = MagicMock(
        side_effect=lambda task: (
            task.instruction
            if not task.context
            else f"{task.instruction}\n\nContext:\n{task.context}"
        )
    )
    return runner


@pytest.fixture
def soul_alpha():
    return make_soul_alpha()


def make_soul_alpha() -> Soul:
    return Soul(
        id="soul_alpha",
        kind="soul",
        name="Dispatch Reviewer Alpha",
        role="Reviewer A",
        system_prompt="You are reviewer A.",
    )


@pytest.fixture
def soul_beta():
    return make_soul_beta()


def make_soul_beta() -> Soul:
    return Soul(
        id="soul_beta",
        kind="soul",
        name="Dispatch Reviewer Beta",
        role="Reviewer B",
        system_prompt="You are reviewer B.",
    )


@pytest.fixture
def soul_gamma_with_model():
    return make_soul_gamma_with_model()


def make_soul_gamma_with_model() -> Soul:
    return Soul(
        id="soul_gamma",
        kind="soul",
        name="Dispatch Reviewer Gamma",
        role="Reviewer C",
        system_prompt="You are reviewer C.",
        model_name="soul-override-model",
    )


@pytest.fixture
def dispatch_task():
    return make_dispatch_task()


def make_dispatch_task() -> dict[str, str]:
    return {"instruction": "coordinate reviewer branches"}


@pytest.fixture
def block_execution_ctx():
    return make_block_execution_ctx()


def make_block_execution_ctx() -> BlockExecutionContext:
    return BlockExecutionContext(
        workflow_name="dispatch_migration_workflow",
        blocks={},
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )


def make_branches(soul_alpha: Soul, soul_beta: Soul) -> list[DispatchBranch]:
    return [
        DispatchBranch(
            exit_id="exit_a",
            label="Exit A",
            soul=soul_alpha,
            task_instruction="Do task A",
        ),
        DispatchBranch(
            exit_id="exit_b",
            label="Exit B",
            soul=soul_beta,
            task_instruction="Do task B",
        ),
    ]


def make_result(
    soul_id: str,
    output: str,
    cost: float = 0.0,
    tokens: int = 0,
    task_id: str = "dispatch-fixture-task",
) -> ExecutionResult:
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def make_dispatch_context(block_id: str, task: dict | None = None) -> BlockContext:
    return BlockContext(
        block_id=block_id,
        instruction=(task or {}).get("instruction", "dispatch"),
        context=None,
        inputs={},
        conversation_history=[],
        soul=None,
        model_name=None,
    )


def setup_runner_side_effect(mock_runner, soul_output_map: dict[str, ExecutionResult]) -> None:
    async def _side_effect(instruction, context, soul, **kwargs):
        return soul_output_map[soul.id]

    mock_runner.execute = AsyncMock(side_effect=_side_effect)


def patch_dispatch_budget_passthrough(monkeypatch) -> None:
    import runsight_core.blocks.dispatch as dispatch_module

    def _fit_to_budget(request, counter):
        return SimpleNamespace(
            instruction=request.instruction,
            context=request.context,
            messages=list(request.conversation_history),
        )

    monkeypatch.setattr(dispatch_module, "fit_to_budget", _fit_to_budget)


def souls_to_branches(souls: list[Soul]) -> list[DispatchBranch]:
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


def make_stateful_dispatch(block_id: str, souls: list[Soul], runner) -> DispatchBlock:
    block = DispatchBlock(block_id, souls_to_branches(souls), runner)
    block.stateful = True
    return block


async def run_block(block, state: WorkflowState) -> WorkflowState:
    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, block.block_id, output)
    return state
