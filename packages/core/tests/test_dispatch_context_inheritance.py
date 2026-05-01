"""
Behavior coverage for DispatchBlock inheriting resolved workflow context.

Owner decision: this suite owns context propagation into dispatch branches. It
uses direct block execution for focused behavior and one parsed workflow case to
cover parser-to-runtime wiring.
"""

from unittest.mock import AsyncMock, patch

import pytest
from conftest import execute_block_for_test
from dispatch_synthesize_helpers import (
    make_completion_response,
    make_dispatch_block,
    make_exec_result,
    make_mock_runner,
    make_researcher_soul,
    patch_fixture_model_budget,
    workflow_fixture_text,
)
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_AGGREGATE_INPUT_FIXTURE = "dispatch-synthesize-aggregate-input.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestDispatchContextInheritance:
    """Resolved workflow context flows to every dispatch branch."""

    @pytest.mark.asyncio
    async def test_branches_inherit_resolved_context(self):
        runner = make_mock_runner()
        dispatch = make_dispatch_block(
            runner,
            researcher_task="Find papers",
            coder_task="Write code",
        )
        dispatch.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}
        runner.execute.side_effect = [
            make_exec_result("dispatch_work_researcher", "researcher", "Research done", 0.01, 20),
            make_exec_result("dispatch_work_coder", "coder", "Code done", 0.01, 20),
        ]
        shared_context = "Project: Quantum Computing Initiative, Budget: $50k"
        state = WorkflowState(shared_memory={"_resolved_inputs": {"context": shared_context}})

        await execute_block_for_test(dispatch, state)

        assert runner.execute.call_count == 2
        for call in runner.execute.call_args_list:
            context_arg = call.args[1]
            assert context_arg is not None
            assert shared_context in (context_arg or "")

    @pytest.mark.asyncio
    async def test_branches_keep_separate_instructions_with_shared_context(self):
        runner = make_mock_runner()
        dispatch = make_dispatch_block(
            runner,
            researcher_task="Find papers on QC",
            coder_task="Implement Grover's algorithm",
        )
        dispatch.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}
        runner.execute.side_effect = [
            make_exec_result("dispatch_work_researcher", "researcher", "Research done", 0.01, 20),
            make_exec_result("dispatch_work_coder", "coder", "Code done", 0.01, 20),
        ]
        context = "Focus on efficiency"
        state = WorkflowState(shared_memory={"_resolved_inputs": {"context": context}})

        await execute_block_for_test(dispatch, state)

        calls = runner.execute.call_args_list
        assert calls[0].args[0] != calls[1].args[0]
        assert calls[0].args[1] == calls[1].args[1]
        assert calls[0].args[1] is not None
        assert context in calls[0].args[1]

    @pytest.mark.asyncio
    async def test_branch_runs_without_context_when_no_resolved_context_exists(self):
        runner = make_mock_runner()
        dispatch = DispatchBlock(
            "dispatch_work",
            [DispatchBranch("researcher", "Research Agent", make_researcher_soul(), "Find papers")],
            runner,
        )
        runner.execute.return_value = make_exec_result(
            "dispatch_work_researcher",
            "researcher",
            "Done",
            0.01,
            20,
        )

        final_state = await execute_block_for_test(dispatch, WorkflowState())

        assert "dispatch_work.researcher" in final_state.results
        assert runner.execute.call_args.args[1] is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_parsed_workflow_passes_resolved_context_to_dispatch_branches(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_messages = []

        async def _capturing_completion(**kwargs):
            messages = kwargs.get("messages", [])
            captured_messages.append(messages)
            return make_completion_response(content="Done", prompt_tokens=10, total_tokens=20)

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.001

        wf = parse_workflow_yaml(workflow_fixture_text(_AGGREGATE_INPUT_FIXTURE))
        dispatch_block = wf.blocks["dispatch_work"]
        dispatch_block.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}
        inner_dispatch = getattr(dispatch_block, "inner_block", None)
        if inner_dispatch is not None:
            inner_dispatch.declared_inputs = dict(dispatch_block.declared_inputs)

        important_context = "IMPORTANT_PROJECT_CONTEXT_XYZ"
        state = WorkflowState(shared_memory={"_resolved_inputs": {"context": important_context}})
        await wf.run(state)

        assert len(captured_messages) >= 2
        for branch_messages in captured_messages[:2]:
            all_content = " ".join(m.get("content", "") for m in branch_messages)
            assert important_context in all_content
