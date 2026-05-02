"""Smoke coverage for mixed Linear -> Dispatch -> Synthesize workflow wiring."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core import DispatchBlock, LinearBlock, SynthesizeBlock
from runsight_core.blocks.dispatch import DispatchBranch
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow


def _souls_to_branches(souls):
    return [
        DispatchBranch(exit_id=s.id, label=s.role, soul=s, task_instruction="Execute task")
        for s in souls
    ]


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner.model_name = None
    runner.execute = AsyncMock()
    return runner


@pytest.fixture
def workflow_souls():
    return {
        "researcher": Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research topics",
        ),
        "reviewer1": Soul(
            id="reviewer1",
            kind="soul",
            name="Reviewer 1",
            role="Reviewer 1",
            system_prompt="Review code",
        ),
        "reviewer2": Soul(
            id="reviewer2",
            kind="soul",
            name="Reviewer 2",
            role="Reviewer 2",
            system_prompt="Review code",
        ),
        "synthesizer": Soul(
            id="synthesizer",
            kind="soul",
            name="Synthesizer",
            role="Synthesizer",
            system_prompt="Combine feedback",
        ),
    }


@pytest.mark.asyncio
async def test_linear_dispatch_synthesize_workflow_smoke(mock_runner, workflow_souls):
    mock_runner.execute.side_effect = [
        ExecutionResult(task_id="research", soul_id="researcher", output="Research findings"),
        ExecutionResult(task_id="review", soul_id="reviewer1", output="Review A"),
        ExecutionResult(task_id="review", soul_id="reviewer2", output="Review B"),
        ExecutionResult(task_id="synthesis", soul_id="synthesizer", output="Combined report"),
    ]

    wf = Workflow("research_review_synthesis_smoke")
    research = LinearBlock("research", workflow_souls["researcher"], mock_runner)
    reviews = DispatchBlock(
        "peer_reviews",
        _souls_to_branches([workflow_souls["reviewer1"], workflow_souls["reviewer2"]]),
        mock_runner,
    )
    synthesis = SynthesizeBlock(
        "final_report",
        ["research", "peer_reviews"],
        workflow_souls["synthesizer"],
        mock_runner,
    )
    wf.add_block(research).add_block(reviews).add_block(synthesis)
    wf.add_transition("research", "peer_reviews")
    wf.add_transition("peer_reviews", "final_report")
    wf.add_transition("final_report", None)
    wf.set_entry("research")

    final_state = await wf.run(WorkflowState(metadata={"workflow_type": "research_pipeline"}))

    assert final_state.results["research"].output == "Research findings"
    assert json.loads(final_state.results["peer_reviews"].output)[0]["output"] == "Review A"
    assert final_state.results["final_report"].output == "Combined report"
    assert final_state.metadata["workflow_type"] == "research_pipeline"
    assert [entry["content"].split("]")[0] + "]" for entry in final_state.execution_log] == [
        "[Block research]",
        "[Block peer_reviews]",
        "[Block final_report]",
    ]
