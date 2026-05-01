"""
Integration coverage for parsed dispatch workflows that feed SynthesizeBlock.

Owner decision: this suite owns the cross-block flow from parsed workflow YAML
through DispatchBlock branch execution into SynthesizeBlock input resolution.
Loop history and context inheritance have their own suites.
"""

from unittest.mock import AsyncMock, patch

import pytest
from conftest import execute_block_for_test
from dispatch_synthesize_helpers import (
    make_completion_response,
    make_dispatch_block,
    make_exec_result,
    make_mock_runner,
    make_synthesizer_soul,
    patch_fixture_model_budget,
    workflow_fixture_text,
)
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_AGGREGATE_INPUT_FIXTURE = "dispatch-synthesize-aggregate-input.yaml"
_PER_EXIT_INPUTS_FIXTURE = "dispatch-synthesize-per-exit-inputs.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestDispatchSynthesizeAggregateWorkflow:
    """Parsed dispatch workflow with aggregate dispatch output passed to synthesize."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_writes_branch_and_synthesis_results(
        self, patched_cost_calculator, patched_completion_call
    ):
        call_count = 0

        async def _completion_for_branch_prompt(**kwargs):
            nonlocal call_count
            call_count += 1
            prompt_text = " ".join(m.get("content", "") for m in kwargs.get("messages", []))

            if "synthesize" in prompt_text.lower() or "=== Output from" in prompt_text:
                return make_completion_response(
                    content="Synthesis: Combined quantum research and Grover implementation.",
                    total_tokens=300,
                )
            if "quantum computing" in prompt_text.lower():
                return make_completion_response(
                    content="Research: Found 3 quantum computing papers.",
                    total_tokens=200,
                )
            if "grover" in prompt_text.lower():
                return make_completion_response(
                    content="Code: Implemented Grover's algorithm.",
                    total_tokens=240,
                )
            return make_completion_response(content="Unexpected fixture branch", total_tokens=100)

        patched_completion_call.side_effect = _completion_for_branch_prompt
        patched_cost_calculator.return_value = 0.01

        wf = parse_workflow_yaml(workflow_fixture_text(_AGGREGATE_INPUT_FIXTURE))
        final_state = await wf.run(WorkflowState())

        assert "dispatch_work.researcher" in final_state.results
        assert "dispatch_work.coder" in final_state.results
        assert "dispatch_work" in final_state.results
        assert "merge_results" in final_state.results

        researcher_output = final_state.results["dispatch_work.researcher"].output
        coder_output = final_state.results["dispatch_work.coder"].output
        synth_output = final_state.results["merge_results"].output
        assert "Research" in researcher_output
        assert "quantum computing" in researcher_output.lower()
        assert "Grover" in coder_output
        assert "Synthesis" in synth_output
        assert final_state.total_cost_usd > 0
        assert final_state.total_tokens > 0
        assert call_count >= 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_dispatch_branches_receive_per_exit_task_prompts(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_prompts = []

        async def _capturing_completion(**kwargs):
            for message in kwargs.get("messages", []):
                if message.get("role") == "user":
                    captured_prompts.append(message["content"])
            return make_completion_response(content="OK")

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.001

        wf = parse_workflow_yaml(workflow_fixture_text(_AGGREGATE_INPUT_FIXTURE))
        await wf.run(WorkflowState())

        dispatch_prompts = captured_prompts[:2]
        assert len(dispatch_prompts) == 2
        assert dispatch_prompts[0] != dispatch_prompts[1]
        assert any("quantum computing" in prompt.lower() for prompt in dispatch_prompts)
        assert any("grover" in prompt.lower() for prompt in dispatch_prompts)

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_synthesize_block_receives_aggregate_dispatch_output(
        self, patched_cost_calculator, patched_completion_call
    ):
        captured_synthesize_prompts = []

        async def _capturing_completion(**kwargs):
            messages = kwargs.get("messages", [])
            prompt_text = " ".join(m.get("content", "") for m in messages)
            if "synthesize" in prompt_text.lower() or "=== Output from" in prompt_text:
                captured_synthesize_prompts.extend(
                    m["content"] for m in messages if m.get("role") == "user"
                )
            return make_completion_response(content="Synthesized result")

        patched_completion_call.side_effect = _capturing_completion
        patched_cost_calculator.return_value = 0.001

        wf = parse_workflow_yaml(workflow_fixture_text(_AGGREGATE_INPUT_FIXTURE))
        await wf.run(WorkflowState())

        assert captured_synthesize_prompts
        assert "dispatch_work" in captured_synthesize_prompts[0]

    @pytest.mark.asyncio
    async def test_dispatch_and_synthesize_totals_accumulate_cost_and_tokens(self):
        runner = make_mock_runner()
        runner.execute.side_effect = [
            make_exec_result(
                "dispatch_work_researcher", "researcher", "Research output", 0.05, 100
            ),
            make_exec_result("dispatch_work_coder", "coder", "Code output", 0.08, 150),
            make_exec_result(
                "merge_results_synthesis",
                "synthesizer",
                "Synthesis output",
                0.10,
                200,
            ),
        ]

        dispatch = make_dispatch_block(
            runner,
            researcher_task="Find papers",
            coder_task="Implement algorithm",
        )
        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work"],
            synthesizer_soul=make_synthesizer_soul(),
            runner=runner,
        )

        state = WorkflowState()
        state = await execute_block_for_test(dispatch, state)
        state = await execute_block_for_test(synthesize, state)

        assert state.total_cost_usd == pytest.approx(0.23)
        assert state.total_tokens == 450


class TestDispatchSynthesizePerExitInputs:
    """SynthesizeBlock reads individual dispatch branch outputs by dotted key."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_accepts_per_exit_synthesize_inputs(
        self, patched_cost_calculator, patched_completion_call
    ):
        patched_completion_call.return_value = make_completion_response(
            content="output",
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
        )
        patched_cost_calculator.return_value = 0.001

        wf = parse_workflow_yaml(workflow_fixture_text(_PER_EXIT_INPUTS_FIXTURE))
        final_state = await wf.run(WorkflowState())

        assert wf.name == "dispatch_synthesize_per_exit_inputs_workflow"
        assert "merge_results" in final_state.results

    @pytest.mark.asyncio
    async def test_synthesize_reads_per_exit_branch_results(self):
        runner = make_mock_runner()
        runner.execute.return_value = make_exec_result(
            "merge_synthesis",
            "synthesizer",
            "Synthesized from individual branches",
            0.05,
            100,
        )
        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work.researcher", "dispatch_work.coder"],
            synthesizer_soul=make_synthesizer_soul(),
            runner=runner,
        )
        state = WorkflowState(
            results={
                "dispatch_work.researcher": BlockResult(
                    output="Research: Found 3 papers.",
                    exit_handle="researcher",
                ),
                "dispatch_work.coder": BlockResult(
                    output="Code: Implemented Grover's algorithm.",
                    exit_handle="coder",
                ),
                "dispatch_work": BlockResult(output='[{"exit_id":"researcher","output":"..."}]'),
            }
        )

        final_state = await execute_block_for_test(synthesize, state)

        context_arg = runner.execute.call_args.args[1]
        assert "merge_results" in final_state.results
        assert "Research: Found 3 papers." in (context_arg or "")
        assert "Code: Implemented Grover's algorithm." in (context_arg or "")
        assert "dispatch_work.researcher" in (context_arg or "")
        assert "dispatch_work.coder" in (context_arg or "")

    @pytest.mark.asyncio
    async def test_synthesize_rejects_missing_per_exit_branch_result(self):
        runner = make_mock_runner()
        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work.researcher", "dispatch_work.coder"],
            synthesizer_soul=make_synthesizer_soul(),
            runner=runner,
        )
        state = WorkflowState(
            results={
                "dispatch_work.researcher": BlockResult(output="Research output"),
            }
        )

        with pytest.raises(ValueError, match="dispatch_work\\.coder.*source result missing"):
            await execute_block_for_test(synthesize, state)
