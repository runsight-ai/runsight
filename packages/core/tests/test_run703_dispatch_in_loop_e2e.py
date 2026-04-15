"""
E2E tests for RUN-703: Dispatch inside Loop + assertions on loop-iterated blocks.

Two acceptance criteria:
  AC1 — LoopBlock with DispatchBlock inner block: loop runs 2 rounds, dispatch
        routes correctly each round, per-round exit results present in final state.
  AC2 — Block with assertions inside loop: observer fires on_block_complete each
        round with the correct per-round state, so assertion evaluation can happen
        per-round. Assertion configs are accessible on the runtime block.

All tests are mocked — no real API calls.
"""

from __future__ import annotations

import json
from textwrap import dedent
from types import SimpleNamespace

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _ScriptedRunner:
    """Deterministic runner for exercising parsed LLM-backed blocks end-to-end.

    Replicates the pattern from test_yaml_dx_e2e.py.
    """

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.model_name = "gpt-4o-mini"
        self.calls: list[tuple[str, str, str | None]] = []
        self.attempts: dict[str, int] = {}

    async def execute(self, instruction: str, context, soul, messages=None, **kwargs):
        soul_id = soul.id
        attempt = self.attempts.get(soul_id, 0) + 1
        self.attempts[soul_id] = attempt
        self.calls.append((soul_id, instruction, context))

        behavior = self.behaviors.get(soul_id)
        if behavior is None:
            output = f"{soul_id}|{instruction}|{context or ''}"
        else:
            output = behavior(attempt, instruction, soul)

        if isinstance(output, BaseException):
            raise output

        return SimpleNamespace(output=str(output), cost_usd=0.0, total_tokens=0, exit_handle=None)


class RecordingObserver:
    """Observer that records all on_block_complete calls with state snapshots."""

    def __init__(self) -> None:
        self.events: list[tuple[str, ...]] = []
        self.block_complete_states: list[tuple[str, str, WorkflowState]] = []

    def on_workflow_start(self, workflow_name: str, state: WorkflowState) -> None:
        self.events.append(("workflow_start", workflow_name))

    def on_block_start(self, workflow_name: str, block_id: str, block_type: str, **kwargs) -> None:
        self.events.append(("block_start", workflow_name, block_id, block_type))

    def on_block_complete(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        state: WorkflowState,
        **kwargs,
    ) -> None:
        self.events.append(("block_complete", workflow_name, block_id, block_type))
        self.block_complete_states.append((workflow_name, block_id, state))

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
    ) -> None:
        self.events.append(("block_error", workflow_name, block_id, block_type, str(error)))

    def on_workflow_complete(
        self, workflow_name: str, state: WorkflowState, duration_s: float
    ) -> None:
        self.events.append(("workflow_complete", workflow_name))

    def on_workflow_error(self, workflow_name: str, error: Exception, duration_s: float) -> None:
        self.events.append(("workflow_error", workflow_name, str(error)))


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(
        id=soul_id,
        role="Tester",
        system_prompt="You are a test agent.",
        model_name="gpt-4o-mini",
    )


def _make_state(**overrides) -> WorkflowState:
    defaults: dict = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_workflow_with_loop(
    name: str,
    loop: LoopBlock,
    *inner_blocks: BaseBlock,
) -> Workflow:
    wf = Workflow(name)
    wf.add_block(loop)
    for block in inner_blocks:
        wf.add_block(block)
    wf.set_entry(loop.block_id)
    wf.add_transition(loop.block_id, None)
    return wf


# ===========================================================================
# AC1 — LoopBlock with DispatchBlock inner block
# ===========================================================================


class TestAC1DispatchInsideLoop:
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

        runner = _ScriptedRunner(
            behaviors={
                "soul_a": _branch_behavior,
                "soul_b": _branch_behavior,
            }
        )

        soul_a = _make_soul("soul_a")
        soul_b = _make_soul("soul_b")

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

        state = _make_state()

        wf = _make_workflow_with_loop("dispatch_loop_wf", loop, dispatch)
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

        runner = _ScriptedRunner(
            behaviors={
                "soul_a": _tracking_behavior,
                "soul_b": _tracking_behavior,
            }
        )

        soul_a = _make_soul("soul_a")
        soul_b = _make_soul("soul_b")

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

        state = _make_state()

        wf = _make_workflow_with_loop("diff_output_wf", loop, dispatch)
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
        runner = _ScriptedRunner(
            behaviors={
                "soul_a": lambda a, i, s: f"output_{a}",
            }
        )

        soul_a = _make_soul("soul_a")

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

        state = _make_state()

        observer = RecordingObserver()
        wf = _make_workflow_with_loop("observer_wf", loop, dispatch)
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
    async def test_dispatch_inside_loop_via_yaml(self, tmp_path):
        """Full YAML-to-execution flow: parse a workflow with a dispatch block
        inside a loop block, then run it with a scripted runner.

        Verifies the parser correctly builds the LoopBlock->DispatchBlock
        composition and the runtime executes both rounds.
        """
        yaml_content = dedent("""\
            version: "1.0"
            souls:
              analyst_a:
                id: analyst_a
                role: Analyst A
                system_prompt: Analyze from perspective A.
              analyst_b:
                id: analyst_b
                role: Analyst B
                system_prompt: Analyze from perspective B.
            blocks:
              multi_dispatch:
                type: dispatch
                exits:
                  - id: port_a
                    label: Perspective A
                    soul_ref: analyst_a
                    task: Analyze from angle A
                  - id: port_b
                    label: Perspective B
                    soul_ref: analyst_b
                    task: Analyze from angle B
              review_loop:
                type: loop
                inner_block_refs:
                  - multi_dispatch
                max_rounds: 2
            workflow:
              name: dispatch_in_loop_yaml
              entry: review_loop
              transitions:
                - from: review_loop
                  to: null
        """)

        wf_path = tmp_path / "dispatch_loop.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        runner = _ScriptedRunner(
            behaviors={
                "analyst_a": lambda attempt, instruction, soul: f"A_round_{attempt}",
                "analyst_b": lambda attempt, instruction, soul: f"B_round_{attempt}",
            }
        )

        workflow = parse_workflow_yaml(str(wf_path), runner=runner)

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


# ===========================================================================
# AC2 — Block with assertions inside loop
# ===========================================================================


class TestAC2AssertionsInsideLoop:
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
        yaml_content = dedent("""\
            version: "1.0"
            souls:
              writer:
                id: writer
                role: Writer
                system_prompt: Write carefully.
            blocks:
              draft:
                type: linear
                soul_ref: writer
                assertions:
                  - type: contains
                    value: "expected keyword"
                  - type: is-json
            workflow:
              name: assertions_test
              entry: draft
              transitions:
                - from: draft
                  to: null
        """)

        wf_path = tmp_path / "assertions.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        runner = _ScriptedRunner()
        workflow = parse_workflow_yaml(str(wf_path), runner=runner)

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
        from unittest.mock import AsyncMock, MagicMock

        from runsight_core.blocks.linear import LinearBlock

        runner = MagicMock()
        runner.model_name = "gpt-4o-mini"

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
            role="Writer",
            system_prompt="Write carefully.",
            model_name="gpt-4o-mini",
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
        state = _make_state()

        wf = _make_workflow_with_loop("assertions_loop_wf", loop, writer)
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
        from unittest.mock import AsyncMock, MagicMock

        from runsight_core.blocks.linear import LinearBlock

        runner = MagicMock()
        runner.model_name = "gpt-4o-mini"

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
            role="Critic",
            system_prompt="Evaluate quality.",
            model_name="gpt-4o-mini",
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
        state = _make_state()

        wf = _make_workflow_with_loop("isolation_wf", loop, critic)
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
    async def test_assertions_accessible_on_block_inside_loop_via_yaml(self, tmp_path):
        """Full YAML path: a block with assertions inside a loop. Verify
        assertions config is accessible and the workflow executes correctly
        with the observer receiving per-round events."""
        yaml_content = dedent("""\
            version: "1.0"
            souls:
              critic:
                id: critic
                role: Quality Critic
                system_prompt: Evaluate quality.
            blocks:
              evaluate:
                type: linear
                soul_ref: critic
                assertions:
                  - type: contains
                    value: "PASS"
                  - type: contains
                    value: "score"
              review_loop:
                type: loop
                inner_block_refs:
                  - evaluate
                max_rounds: 2
            workflow:
              name: assertions_in_loop_yaml
              entry: review_loop
              transitions:
                - from: review_loop
                  to: null
        """)

        wf_path = tmp_path / "assertions_loop.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        call_idx = {"n": 0}

        def critic_behavior(attempt, instruction, soul):
            call_idx["n"] += 1
            if call_idx["n"] == 1:
                return "FAIL: score 30"
            return "PASS: score 95"

        runner = _ScriptedRunner(behaviors={"critic": critic_behavior})

        workflow = parse_workflow_yaml(str(wf_path), runner=runner)

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

    @pytest.mark.asyncio
    async def test_dispatch_with_assertions_inside_loop(self, tmp_path):
        """Combined scenario: a dispatch block with assertions inside a loop.
        Verifies both AC1 (dispatch routing per round) and AC2 (assertions
        config accessible + observer fires per round) together."""
        yaml_content = dedent("""\
            version: "1.0"
            souls:
              reviewer:
                id: reviewer
                role: Reviewer
                system_prompt: Review the content.
            blocks:
              review_dispatch:
                type: dispatch
                exits:
                  - id: quality
                    label: Quality Review
                    soul_ref: reviewer
                    task: Review for quality
                assertions:
                  - type: contains
                    value: "reviewed"
              review_loop:
                type: loop
                inner_block_refs:
                  - review_dispatch
                max_rounds: 2
            workflow:
              name: dispatch_assertions_loop
              entry: review_loop
              transitions:
                - from: review_loop
                  to: null
        """)

        wf_path = tmp_path / "dispatch_assertions_loop.yaml"
        wf_path.write_text(yaml_content, encoding="utf-8")

        runner = _ScriptedRunner(
            behaviors={
                "reviewer": lambda attempt, instruction, soul: f"reviewed_round_{attempt}",
            }
        )

        workflow = parse_workflow_yaml(str(wf_path), runner=runner)

        # Assertions bridged to dispatch block
        dispatch_block = workflow._blocks["review_dispatch"]
        assert dispatch_block.assertions is not None
        assert len(dispatch_block.assertions) == 1
        assert dispatch_block.assertions[0]["type"] == "contains"

        # Run with observer
        observer = RecordingObserver()
        state = WorkflowState()
        final = await workflow.run(state, observer=observer)

        # Loop completed 2 rounds
        loop_meta = final.shared_memory["__loop__review_loop"]
        assert loop_meta["rounds_completed"] == 2

        # Observer captured 2 block_complete events for review_dispatch
        dispatch_snapshots = [
            st
            for wf_name, block_id, st in observer.block_complete_states
            if block_id == "review_dispatch"
        ]
        assert len(dispatch_snapshots) == 2

        # Round 1 and round 2 have different outputs
        r1_combined = json.loads(dispatch_snapshots[0].results["review_dispatch"].output)
        r2_combined = json.loads(dispatch_snapshots[1].results["review_dispatch"].output)
        assert "reviewed_round_1" in r1_combined[0]["output"]
        assert "reviewed_round_2" in r2_combined[0]["output"]
