"""Smoke coverage for LinearBlock -> runner -> LLM client -> WorkflowState wiring."""

from unittest.mock import patch

import pytest
from runsight_core import LinearBlock
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.state import WorkflowState


async def _run_block(block, state: WorkflowState) -> WorkflowState:
    from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)
    if isinstance(output, WorkflowState):
        return output
    if isinstance(output, BlockOutput):
        return apply_block_output(state, block.block_id, output)
    return state


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_single_linear_block_updates_state_from_patched_llm(mock_achat):
    mock_achat.return_value = {
        "content": "Research complete: Found 5 relevant papers on quantum computing.",
        "cost_usd": 0.1,
        "total_tokens": 150,
    }
    soul = Soul(
        id="researcher",
        kind="soul",
        name="Researcher",
        role="Research Analyst",
        system_prompt="You summarize academic papers.",
        provider="openai",
        model_name="gpt-4o",
    )
    runner = RunsightTeamRunner(model_name="gpt-4o")
    block = LinearBlock("research_block", soul, runner)
    block.declared_inputs = {"instruction": "shared_memory._resolved_inputs.instruction"}
    state = WorkflowState(
        shared_memory={
            "_resolved_inputs": {
                "instruction": "Research quantum computing papers published in 2024"
            }
        },
        metadata={"workflow_name": "research_pipeline"},
    )

    final_state = await _run_block(block, state)

    assert final_state.results["research_block"].output.startswith("Research complete")
    assert final_state.metadata["workflow_name"] == "research_pipeline"
    assert final_state.total_cost_usd == 0.1
    assert final_state.total_tokens == 150
    assert "[Block research_block]" in final_state.execution_log[0]["content"]

    call_kwargs = mock_achat.call_args.kwargs
    assert "quantum computing" in call_kwargs["messages"][0]["content"]
    assert call_kwargs["system_prompt"] == soul.system_prompt
