"""Integration coverage for assertion observers on blocks inside LoopBlock."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from loop_integration_helpers import (
    RecordingObserver,
    ScriptedRunner,
    make_state,
    make_workflow_with_loop,
    patch_fixture_model_budget,
)
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState
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


class TestAssertionsInsideLoop:
    """Block with assertion configs inside a loop: the observer fires
    on_block_complete each round with per-round state, enabling assertion
    evaluation per round.

    Assertions at runtime are evaluated by observers (EvalObserver in apps/api).
    The core engine's contract is:
    1. Assertion configs are accessible on the runtime block
    2. The observer fires on_block_complete for each round with the correct state
    3. The state at each on_block_complete contains the block's output for that round

    These tests verify that contract at the core level.
    """

    @pytest.mark.asyncio
    async def test_assertion_configs_bridged_to_runtime_block_from_yaml(self, tmp_path):
        """When a block definition has assertions: config in YAML, the parser
        bridges those configs onto the runtime block as block.assertions."""
        yaml_content = workflow_fixture_text("loop-block-assertions.yaml")

        wf_path = tmp_path / "assertions.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        runner = ScriptedRunner()
        workflow = parse_workflow_yaml(
            str(wf_path),
            runner=runner,
            api_keys={"openai": "dummy-openai-key"},
        )

        # The draft block should have assertions attached
        draft_block = workflow._blocks["draft"]
        assert hasattr(draft_block, "assertions")
        assert draft_block.assertions is not None
        assert len(draft_block.assertions) == 2
        assert draft_block.assertions[0]["type"] == "contains"
        assert draft_block.assertions[0]["value"] == "expected keyword"
        assert draft_block.assertions[1]["type"] == "is-json"

    @pytest.mark.asyncio
    async def test_observer_fires_per_round_for_block_inside_loop(self):
        """When a block inside a LoopBlock has assertions config, the observer
        should fire on_block_complete on each round. Each call should carry
        the state reflecting that round's output.

        This is the core contract that enables EvalObserver to evaluate
        assertions per round.
        """
        runner = MagicMock()
        runner.model_name = "fixture-dispatch-loop-model"

        call_count = {"n": 0}

        async def _mock_execute(instruction, context, soul, messages=None, **kwargs):
            call_count["n"] += 1
            # Round 1: output fails assertion (no keyword)
            # Round 2: output passes assertion (has keyword)
            if call_count["n"] == 1:
                output = "This output is missing the target."
            else:
                output = "This output contains expected keyword."
            return ExecutionResult(
                task_id="mock",
                soul_id=soul.id,
                output=output,
                cost_usd=0.01,
                total_tokens=50,
            )

        runner.execute = AsyncMock(side_effect=_mock_execute)

        soul = Soul(
            id="writer",
            kind="soul",
            name="Writer",
            role="Writer",
            system_prompt="Write carefully.",
            model_name="fixture-dispatch-loop-model",
        )

        writer = LinearBlock("draft", soul, runner)
        # Attach assertions config (as the parser would do)
        writer.assertions = [
            {"type": "contains", "value": "expected keyword"},
        ]

        loop = LoopBlock(
            "review_loop",
            inner_block_refs=["draft"],
            max_rounds=2,
        )

        observer = RecordingObserver()
        state = make_state()

        wf = make_workflow_with_loop("assertions_loop_wf", loop, writer)
        await wf.run(state, observer=observer)

        # Observer fired on_block_complete for 'draft' on each round
        draft_completes = [
            (wf_name, block_id, st)
            for wf_name, block_id, st in observer.block_complete_states
            if block_id == "draft"
        ]
        assert len(draft_completes) == 2

        # Round 1 state: output should NOT contain "expected keyword"
        round1_state = draft_completes[0][2]
        round1_output = round1_state.results["draft"].output
        assert "expected keyword" not in round1_output
        assert "missing the target" in round1_output

        # Round 2 state: output SHOULD contain "expected keyword"
        round2_state = draft_completes[1][2]
        round2_output = round2_state.results["draft"].output
        assert "expected keyword" in round2_output

        # The block's assertions config is still accessible (observer can read it)
        assert writer.assertions is not None
        assert writer.assertions[0]["type"] == "contains"

    @pytest.mark.asyncio
    async def test_observer_per_round_state_isolation(self):
        """The state passed to the observer at each round should reflect only
        that round's output for the inner block, not a stale value from a
        previous round.

        This ensures that per-round assertion evaluation sees the correct output.
        """
        runner = MagicMock()
        runner.model_name = "fixture-dispatch-loop-model"

        call_idx = {"n": 0}
        outputs = ["FAIL: score is 20", "PASS: score is 95"]

        async def _mock_execute(instruction, context, soul, messages=None, **kwargs):
            output = outputs[call_idx["n"]]
            call_idx["n"] += 1
            return ExecutionResult(
                task_id="mock",
                soul_id=soul.id,
                output=output,
                cost_usd=0.01,
                total_tokens=50,
            )

        runner.execute = AsyncMock(side_effect=_mock_execute)

        soul = Soul(
            id="critic",
            kind="soul",
            name="Critic",
            role="Critic",
            system_prompt="Evaluate quality.",
            model_name="fixture-dispatch-loop-model",
        )

        critic = LinearBlock("quality_check", soul, runner)
        critic.assertions = [
            {"type": "contains", "value": "PASS"},
        ]

        loop = LoopBlock(
            "eval_loop",
            inner_block_refs=["quality_check"],
            max_rounds=2,
        )

        observer = RecordingObserver()
        state = make_state()

        wf = make_workflow_with_loop("isolation_wf", loop, critic)
        await wf.run(state, observer=observer)

        # Get per-round states
        qc_snapshots = [
            st
            for wf_name, block_id, st in observer.block_complete_states
            if block_id == "quality_check"
        ]
        assert len(qc_snapshots) == 2

        # Round 1: FAIL output
        r1_output = qc_snapshots[0].results["quality_check"].output
        assert "FAIL" in r1_output
        assert "PASS" not in r1_output

        # Round 2: PASS output
        r2_output = qc_snapshots[1].results["quality_check"].output
        assert "PASS" in r2_output
        assert "FAIL" not in r2_output

    @pytest.mark.asyncio
    async def test_assertions_accessible_on_block_inside_loop_via_yaml(self, tmp_path, monkeypatch):
        """Full YAML path: a block with assertions inside a loop. Verify
        assertions config is accessible and the workflow executes correctly
        with the observer receiving per-round events."""
        yaml_content = workflow_fixture_text("loop-assertion-observer.yaml")

        wf_path = tmp_path / "assertions_loop.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        call_idx = {"n": 0}

        def critic_behavior(attempt, instruction, soul):
            call_idx["n"] += 1
            if call_idx["n"] == 1:
                return "FAIL: score 30"
            return "PASS: score 95"

        runner = ScriptedRunner(behaviors={"critic": critic_behavior})

        completion_outputs = iter(["FAIL: score 30", "PASS: score 95"])

        async def _fake_completion(**_kwargs):
            return _completion_response(next(completion_outputs))

        monkeypatch.setattr("runsight_core.llm.client.acompletion", _fake_completion)
        monkeypatch.setattr("runsight_core.llm.client.completion_cost", lambda **_: 0.0)

        workflow = parse_workflow_yaml(
            str(wf_path),
            runner=runner,
            api_keys={"openai": "dummy-openai-key"},
        )

        # Verify assertions are bridged to runtime block
        evaluate_block = workflow._blocks["evaluate"]
        assert evaluate_block.assertions is not None
        assert len(evaluate_block.assertions) == 2

        # Run with observer
        observer = RecordingObserver()
        state = WorkflowState()
        final = await workflow.run(state, observer=observer)

        # Loop ran both rounds
        loop_meta = final.shared_memory["__loop__review_loop"]
        assert loop_meta["rounds_completed"] == 2

        # Observer captured per-round block_complete for evaluate block
        eval_completes = [
            st for wf_name, block_id, st in observer.block_complete_states if block_id == "evaluate"
        ]
        assert len(eval_completes) == 2

        # Round 1: FAIL output
        assert "FAIL" in eval_completes[0].results["evaluate"].output
        # Round 2: PASS output
        assert "PASS" in eval_completes[1].results["evaluate"].output
