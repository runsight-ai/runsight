"""Integration coverage for DispatchBlock behavior inside LoopBlock."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from loop_integration_helpers import (
    RecordingObserver,
    ScriptedRunner,
    make_soul,
    make_state,
    make_workflow_with_loop,
    patch_fixture_model_budget,
)
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from workflow_fixture_helpers import workflow_fixture_text


def _completion_response(content: str):
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = 0
    usage.completion_tokens = 0
    usage.total_tokens = 0

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestDispatchInsideLoop:
    """LoopBlock runs 2 rounds with a DispatchBlock as inner block.

    The scripted LLM picks different exit ports on different rounds. Verify
    per-round exit results show correct routing and the loop completes both
    rounds.
    """

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_runs_both_rounds(self):
        """A DispatchBlock inside a LoopBlock should execute for each round.
        With no break_on_exit configured that matches, loop runs to max_rounds=2.

        Round 1: both branches produce 'round_1_output_X'
        Round 2: both branches produce 'round_2_output_X'
        """
        call_count = {"n": 0}

        def _branch_behavior(attempt, instruction, soul):
            call_count["n"] += 1
            return f"round_{attempt}_output_{soul.id}"

        runner = ScriptedRunner(
            behaviors={
                "soul_a": _branch_behavior,
                "soul_b": _branch_behavior,
            }
        )

        soul_a = make_soul("soul_a")
        soul_b = make_soul("soul_b")

        dispatch = DispatchBlock(
            block_id="dispatcher",
            branches=[
                DispatchBranch(
                    exit_id="branch_a",
                    label="Branch A",
                    soul=soul_a,
                    task_instruction="Do task A",
                ),
                DispatchBranch(
                    exit_id="branch_b",
                    label="Branch B",
                    soul=soul_b,
                    task_instruction="Do task B",
                ),
            ],
            runner=runner,
        )

        loop = LoopBlock(
            "dispatch_loop",
            inner_block_refs=["dispatcher"],
            max_rounds=2,
        )

        state = make_state()

        wf = make_workflow_with_loop("dispatch_loop_wf", loop, dispatch)
        final = await wf.run(state)

        # Loop ran 2 rounds (no break)
        loop_meta = final.shared_memory["__loop__dispatch_loop"]
        assert loop_meta["rounds_completed"] == 2
        assert loop_meta["broke_early"] is False

        # Per-exit results from the LAST round are present
        assert "dispatcher.branch_a" in final.results
        assert "dispatcher.branch_b" in final.results

        per_exit_a = final.results["dispatcher.branch_a"]
        per_exit_b = final.results["dispatcher.branch_b"]
        assert isinstance(per_exit_a, BlockResult)
        assert isinstance(per_exit_b, BlockResult)

        # Round 2 results (latest) should be in state
        assert "round_2" in per_exit_a.output
        assert "round_2" in per_exit_b.output

        # Exit handles on per-exit results should be the exit_ids
        assert per_exit_a.exit_handle == "branch_a"
        assert per_exit_b.exit_handle == "branch_b"

        # Combined result should be present
        combined = final.results["dispatcher"]
        assert isinstance(combined, BlockResult)
        combined_data = json.loads(combined.output)
        assert len(combined_data) == 2
        exit_ids = {entry["exit_id"] for entry in combined_data}
        assert exit_ids == {"branch_a", "branch_b"}

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_different_outputs_each_round(self):
        """Verify that the scripted runner produces different outputs per round,
        demonstrating that the dispatch executes fresh each round, not cached."""

        def _tracking_behavior(attempt, instruction, soul):
            output = f"attempt_{attempt}_by_{soul.id}"
            return output

        runner = ScriptedRunner(
            behaviors={
                "soul_a": _tracking_behavior,
                "soul_b": _tracking_behavior,
            }
        )

        soul_a = make_soul("soul_a")
        soul_b = make_soul("soul_b")

        dispatch = DispatchBlock(
            block_id="dispatcher",
            branches=[
                DispatchBranch(exit_id="port_a", label="A", soul=soul_a, task_instruction="Task A"),
                DispatchBranch(exit_id="port_b", label="B", soul=soul_b, task_instruction="Task B"),
            ],
            runner=runner,
        )

        loop = LoopBlock(
            "dispatch_loop",
            inner_block_refs=["dispatcher"],
            max_rounds=2,
        )

        state = make_state()

        wf = make_workflow_with_loop("diff_output_wf", loop, dispatch)
        final = await wf.run(state)

        # Each soul gets called twice (once per round)
        assert runner.attempts["soul_a"] == 2
        assert runner.attempts["soul_b"] == 2

        # The final per-exit results should reflect round 2 (attempt 2)
        assert "attempt_2_by_soul_a" in final.results["dispatcher.port_a"].output
        assert "attempt_2_by_soul_b" in final.results["dispatcher.port_b"].output

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_observer_fires_each_round(self):
        """The observer should receive on_block_complete for the dispatcher block
        on each round of the loop."""
        runner = ScriptedRunner(
            behaviors={
                "soul_a": lambda a, i, s: f"output_{a}",
            }
        )

        soul_a = make_soul("soul_a")

        dispatch = DispatchBlock(
            block_id="dispatcher",
            branches=[
                DispatchBranch(exit_id="port_a", label="A", soul=soul_a, task_instruction="Task A"),
            ],
            runner=runner,
        )

        loop = LoopBlock(
            "dispatch_loop",
            inner_block_refs=["dispatcher"],
            max_rounds=2,
        )

        state = make_state()

        observer = RecordingObserver()
        wf = make_workflow_with_loop("observer_wf", loop, dispatch)
        await wf.run(state, observer=observer)

        # Filter observer events for the dispatcher block
        dispatch_completes = [
            ev for ev in observer.events if ev[0] == "block_complete" and ev[2] == "dispatcher"
        ]
        # Should fire twice — once per round
        assert len(dispatch_completes) == 2

        # Each on_block_complete captured a state snapshot
        dispatch_state_snapshots = [
            (wf_name, block_id, st)
            for wf_name, block_id, st in observer.block_complete_states
            if block_id == "dispatcher"
        ]
        assert len(dispatch_state_snapshots) == 2

        # Round 1 state should have round 1 output, round 2 state should have round 2
        round1_state = dispatch_state_snapshots[0][2]
        round2_state = dispatch_state_snapshots[1][2]
        assert "output_1" in round1_state.results["dispatcher.port_a"].output
        assert "output_2" in round2_state.results["dispatcher.port_a"].output

    @pytest.mark.asyncio
    async def test_dispatch_inside_loop_via_yaml(self, tmp_path, monkeypatch):
        """Full YAML-to-execution flow: parse a workflow with a dispatch block
        inside a loop block, then run it with a scripted runner.

        Verifies the parser correctly builds the LoopBlock->DispatchBlock
        composition and the runtime executes both rounds.
        """
        yaml_content = workflow_fixture_text("dispatch-inside-loop.yaml")

        wf_path = tmp_path / "dispatch_loop.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        runner = ScriptedRunner(
            behaviors={
                "analyst_a": lambda attempt, instruction, soul: f"A_round_{attempt}",
                "analyst_b": lambda attempt, instruction, soul: f"B_round_{attempt}",
            }
        )

        attempts = {"a": 0, "b": 0}

        async def _fake_completion(**kwargs):
            message_blob = json.dumps(kwargs.get("messages", []))
            if "angle A" in message_blob or "perspective A" in message_blob:
                attempts["a"] += 1
                return _completion_response(f"A_round_{attempts['a']}")
            attempts["b"] += 1
            return _completion_response(f"B_round_{attempts['b']}")

        monkeypatch.setattr("runsight_core.llm.client.acompletion", _fake_completion)
        monkeypatch.setattr("runsight_core.llm.client.completion_cost", lambda **_: 0.0)

        workflow = parse_workflow_yaml(
            str(wf_path),
            runner=runner,
            api_keys={"openai": "dummy-openai-key"},
        )

        state = WorkflowState()
        final = await workflow.run(state)

        # Loop completed 2 rounds
        loop_meta = final.shared_memory["__loop__review_loop"]
        assert loop_meta["rounds_completed"] == 2
        assert loop_meta["broke_early"] is False

        # Per-exit results present with round 2 output
        assert "multi_dispatch.port_a" in final.results
        assert "multi_dispatch.port_b" in final.results
        assert "A_round_2" in final.results["multi_dispatch.port_a"].output
        assert "B_round_2" in final.results["multi_dispatch.port_b"].output
