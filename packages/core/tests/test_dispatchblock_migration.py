"""DispatchBlock BlockContext/BlockOutput migration compatibility.

Owner: packages/core DispatchBlock runtime migration.
Boundary: temporary compatibility coverage for DispatchBlock execution through
BlockContext, BlockOutput, apply_block_output, build_block_context, and
workflow.execute_block during the migration.
Exit criteria: remove this suite once all DispatchBlock callers exclusively use
the BlockContext/BlockOutput contract and owner suites cover the public
DispatchBlock behavior.
"""

import json
from unittest.mock import patch

import pytest
from dispatch_block_helpers import (
    make_block_execution_ctx,
    make_branches,
    make_dispatch_context,
    make_dispatch_task,
    make_mock_runner,
    make_result,
    make_soul_alpha,
    make_soul_beta,
    setup_runner_side_effect,
)
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.dispatch import DispatchBlock
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import execute_block


def _dispatch_case():
    runner = make_mock_runner()
    alpha = make_soul_alpha()
    beta = make_soul_beta()
    task = make_dispatch_task()
    block = DispatchBlock("review_dispatch_block", make_branches(alpha, beta), runner)
    return runner, alpha, beta, task, block


# BlockContext migration compatibility


@pytest.mark.asyncio
async def test_dispatchblock_execute_accepts_block_context_and_returns_block_output():
    mock_runner, _, _, dispatch_task, block = _dispatch_case()
    setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": make_result("soul_alpha", "Alpha output.", cost=0.01, tokens=100),
            "soul_beta": make_result("soul_beta", "Beta output.", cost=0.02, tokens=200),
        },
    )
    ctx = make_dispatch_context("review_dispatch_block", dispatch_task)

    result = await block.execute(ctx)

    assert isinstance(result, BlockOutput)
    assert not hasattr(result, "current_task")


@pytest.mark.asyncio
async def test_dispatchblock_execute_with_block_context_does_not_mutate_input():
    mock_runner, _, _, dispatch_task, block = _dispatch_case()
    setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": make_result("soul_alpha", "Alpha."),
            "soul_beta": make_result("soul_beta", "Beta."),
        },
    )
    ctx = make_dispatch_context("review_dispatch_block", dispatch_task)
    original_inputs = dict(ctx.inputs)
    original_history = list(ctx.conversation_history)

    await block.execute(ctx)

    assert ctx.inputs == original_inputs
    assert ctx.conversation_history == original_history


def test_build_block_context_for_dispatchblock_returns_migration_context():
    _, _, _, _, block = _dispatch_case()
    ctx = build_block_context(block, WorkflowState())

    assert isinstance(ctx, BlockContext)
    assert ctx.block_id == "review_dispatch_block"
    assert ctx.instruction == "Do task A"


def test_build_block_context_for_dispatchblock_resolves_step_declared_inputs():
    _, _, _, _, block = _dispatch_case()
    state = WorkflowState(results={"source": BlockResult(output="declared context")})
    step = Step(block=block, declared_inputs={"context": "source"})

    ctx = build_block_context(block, state, step=step)

    assert ctx.inputs == {"context": "declared context"}
    assert ctx.context == "declared context"


# BlockOutput migration compatibility


@pytest.mark.asyncio
async def test_dispatchblock_block_output_applies_combined_and_per_exit_results():
    mock_runner, _, _, dispatch_task, block = _dispatch_case()
    setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": make_result("soul_alpha", "Alpha."),
            "soul_beta": make_result("soul_beta", "Beta."),
        },
    )
    output = await block.execute(make_dispatch_context("review_dispatch_block", dispatch_task))

    assert isinstance(output, BlockOutput)
    new_state = apply_block_output(WorkflowState(), "review_dispatch_block", output)

    combined = json.loads(new_state.results["review_dispatch_block"].output)
    assert {item["exit_id"] for item in combined} == {"exit_a", "exit_b"}
    assert set(new_state.results) == {
        "review_dispatch_block",
        "review_dispatch_block.exit_a",
        "review_dispatch_block.exit_b",
    }


@pytest.mark.asyncio
async def test_workflow_execute_block_uses_block_context_migration_path():
    mock_runner, _, _, dispatch_task, block = _dispatch_case()
    setup_runner_side_effect(
        mock_runner,
        {
            "soul_alpha": make_result("soul_alpha", "Alpha.", cost=0.01, tokens=100),
            "soul_beta": make_result("soul_beta", "Beta.", cost=0.02, tokens=200),
        },
    )

    with (
        patch(
            "runsight_core.workflow.build_block_context", wraps=build_block_context
        ) as mock_build,
        patch("runsight_core.workflow.apply_block_output", wraps=apply_block_output) as mock_apply,
    ):
        result_state = await execute_block(block, WorkflowState(), make_block_execution_ctx())

    assert mock_build.called
    assert mock_apply.called
    assert "review_dispatch_block" in result_state.results
