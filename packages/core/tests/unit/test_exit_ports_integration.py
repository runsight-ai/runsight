"""
Failing tests for RUN-271: Update existing YAML workflows + integration tests for exit ports.

This ticket is the capstone of the exit-port series (RUN-266..270). It verifies:
- All existing YAML workflow files declare exits on gate blocks
- Loop blocks containing gates use break_on_exit / retry_on_exit
- Full integration chain: YAML -> parse -> build -> execute -> exit_handle routing

Tests cover:
- AC1: All existing YAML workflows parse and validate
- AC2: All existing tests pass (updated for new model)
- AC3: Gate standalone routing works end-to-end
- AC4: Gate-in-loop routing works end-to-end
- AC5: output_conditions -> exit_handle -> conditional_transitions chain works
- AC6: Validation catches all invalid configurations
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.primitives import Soul, Task
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import ExitDef

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CUSTOM_WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "custom" / "workflows"


# ---------------------------------------------------------------------------
# Helpers: mock runner and blocks
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(id=soul_id, role="Test", system_prompt="Test prompt")


class StubBlock(BaseBlock):
    """Minimal block that stores a fixed output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self._output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
            }
        )


class ExitHandleBlock(BaseBlock):
    """Block whose execute() stores a BlockResult with a specific exit_handle."""

    def __init__(self, block_id: str, exit_handle: str, output: str = "done"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=self._output,
                        exit_handle=self._exit_handle,
                    ),
                },
            }
        )


class JsonOutputBlock(BaseBlock):
    """Block that stores a JSON-string BlockResult (no exit_handle set)."""

    def __init__(self, block_id: str, data: dict):
        super().__init__(block_id)
        self._data = data

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._data)),
                },
            }
        )


def _fresh_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


# ==============================================================================
# AC1: All existing YAML workflows parse and validate
# ==============================================================================


class TestExistingYamlWorkflowsParse:
    """AC1: Every YAML file in custom/workflows/ must parse and validate
    after the exit-port updates (exits on gates, break_on_exit on loops, etc.)."""

    def test_custom_workflows_dir_exists(self):
        """Sanity check: custom/workflows/ directory exists."""
        assert CUSTOM_WORKFLOWS_DIR.exists(), (
            f"custom/workflows/ directory not found at {CUSTOM_WORKFLOWS_DIR}"
        )

    def test_all_yaml_files_found(self):
        """At least two YAML files exist in fixtures/custom/workflows/."""
        yaml_files = list(CUSTOM_WORKFLOWS_DIR.glob("*.yaml"))
        assert len(yaml_files) >= 2, (
            f"Expected at least 2 YAML files in {CUSTOM_WORKFLOWS_DIR}, found {len(yaml_files)}"
        )

    def test_mockup_pipeline_parses_successfully(self):
        """mockup_pipeline.yaml must parse via parse_workflow_yaml without errors.

        Note: This file references a child workflow via workflow_ref.
        so it needs a WorkflowRegistry. We test the YAML structure directly.
        """
        yaml_path = CUSTOM_WORKFLOWS_DIR / "mockup_pipeline.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        # Verify basic structure is valid
        assert "workflow" in data
        assert "blocks" in data


# ==============================================================================
# AC3: Gate standalone routing works end-to-end
# ==============================================================================


class TestGateStandaloneRoutingE2E:
    """AC3: Gate block used standalone (not in a loop) with conditional_transitions."""

    @pytest.mark.asyncio
    async def test_gate_pass_routes_to_success_block(self):
        """Gate returns exit_handle='pass' -> conditional_transition routes to on_pass."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="draft",
            runner=runner,
        )
        on_pass = StubBlock("on_pass", output="success_path")
        on_fail = StubBlock("on_fail", output="failure_path")

        wf = Workflow(name="gate_standalone_pass")
        wf.add_block(StubBlock("draft", output="Some content"))
        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_fail)
        wf.set_entry("draft")

        wf.add_transition("draft", "quality_gate")
        wf.add_conditional_transition(
            "quality_gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_fail"},
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_fail", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="test", context="test"),
        )
        # Pre-seed draft result since gate reads eval_key from results
        state = state.model_copy(update={"results": {"draft": BlockResult(output="Some content")}})

        final = await wf.run(state)

        assert final.results["quality_gate"].exit_handle == "pass"
        assert "on_pass" in final.results, "Should route to on_pass via exit_handle='pass'"
        assert "on_fail" not in final.results, "Should NOT route to on_fail"

    @pytest.mark.asyncio
    async def test_gate_fail_routes_to_failure_block(self):
        """Gate returns exit_handle='fail' -> conditional_transition routes to on_fail."""
        runner = _mock_runner("FAIL: needs improvement")
        gate = GateBlock(
            block_id="quality_gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="draft",
            runner=runner,
        )
        on_pass = StubBlock("on_pass", output="success_path")
        on_fail = StubBlock("on_fail", output="failure_path")

        wf = Workflow(name="gate_standalone_fail")
        wf.add_block(StubBlock("draft", output="Bad content"))
        wf.add_block(gate)
        wf.add_block(on_pass)
        wf.add_block(on_fail)
        wf.set_entry("draft")

        wf.add_transition("draft", "quality_gate")
        wf.add_conditional_transition(
            "quality_gate",
            {"pass": "on_pass", "fail": "on_fail", "default": "on_fail"},
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_fail", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="test", context="test"),
        )
        state = state.model_copy(update={"results": {"draft": BlockResult(output="Bad content")}})

        final = await wf.run(state)

        assert final.results["quality_gate"].exit_handle == "fail"
        assert "on_fail" in final.results, "Should route to on_fail via exit_handle='fail'"
        assert "on_pass" not in final.results, "Should NOT route to on_pass"

    @pytest.mark.asyncio
    async def test_gate_standalone_default_fallback(self):
        """If gate exit_handle is somehow not in the map, 'default' is used."""
        wf = Workflow(name="gate_default_fallback")

        gate = ExitHandleBlock("gate", exit_handle="unknown_value", output="gate out")
        fallback = StubBlock("fallback", output="default_route")

        wf.add_block(gate)
        wf.add_block(fallback)
        wf.set_entry("gate")

        wf.add_conditional_transition(
            "gate",
            {"pass": "fallback", "fail": "fallback", "default": "fallback"},
        )
        wf.add_transition("fallback", None)

        final = await wf.run(_fresh_state())

        assert "fallback" in final.results


# ==============================================================================
# AC4: Gate-in-loop routing works end-to-end
# ==============================================================================


class TestGateInLoopRoutingE2E:
    """AC4: Gate inside a LoopBlock with break_on_exit / retry_on_exit."""

    @pytest.mark.asyncio
    async def test_gate_pass_triggers_break_on_exit(self):
        """Gate inside loop: exit_handle='pass' matches break_on_exit -> loop exits early."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=3,
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_break")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="Write and review", context="test"),
        )

        final = await wf.run(state)

        # Gate passed -> loop should have broken early
        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("broke_early") is True, (
            "Loop should break early when gate exit_handle='pass' matches break_on_exit"
        )
        assert loop_meta.get("rounds_completed") == 1, (
            "Loop should complete only 1 round since gate passed immediately"
        )
        assert final.results["gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_gate_fail_triggers_retry_on_exit(self):
        """Gate inside loop: exit_handle='fail' matches retry_on_exit -> loop retries.
        After max_rounds, loop exits normally (no break)."""
        runner = _mock_runner("FAIL: needs work")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=2,
            retry_on_exit="fail",
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_retry")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="Write and review", context="test"),
        )

        final = await wf.run(state)

        # Gate always fails -> retry_on_exit triggers retry -> exhausts max_rounds
        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should exhaust max_rounds when gate always fails and retry_on_exit='fail'"
        )
        assert loop_meta.get("broke_early") is False, (
            "Loop should NOT break early when gate always fails"
        )

    @pytest.mark.asyncio
    async def test_gate_fail_then_pass_in_loop(self):
        """Gate fails first round (retry), passes second round (break).

        Uses a runner that returns FAIL on first call, PASS on second.
        """
        call_count = {"n": 0}

        async def _side_effect(task, soul):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return ExecutionResult(
                    task_id="test",
                    soul_id="test",
                    output="FAIL: first attempt bad",
                    cost_usd=0.01,
                    total_tokens=100,
                )
            return ExecutionResult(
                task_id="test",
                soul_id="test",
                output="PASS",
                cost_usd=0.01,
                total_tokens=100,
            )

        runner = MagicMock(spec=RunsightTeamRunner)
        runner.model_name = "gpt-4o"
        runner.execute_task = AsyncMock(side_effect=_side_effect)

        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=5,
            retry_on_exit="fail",
            break_on_exit="pass",
        )

        wf = Workflow(name="gate_in_loop_fail_then_pass")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.add_block(StubBlock("done", output="finished"))
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", "done")
        wf.add_transition("done", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="Write and review", context="test"),
        )

        final = await wf.run(state)

        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("broke_early") is True, (
            "Loop should break early on second round when gate passes"
        )
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should complete exactly 2 rounds (fail, then pass)"
        )
        assert final.results["gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_loop_without_break_or_retry_falls_through_to_break_condition(self):
        """Loop with gate but NO break_on_exit/retry_on_exit: the gate exit_handle
        is ignored by the loop, and it falls through to break_condition or max_rounds."""
        runner = _mock_runner("PASS")
        gate = GateBlock(
            block_id="gate",
            gate_soul=_make_soul("evaluator"),
            eval_key="writer",
            runner=runner,
        )
        writer = StubBlock("writer", output="Draft content")

        # No break_on_exit, no retry_on_exit -> loop runs all max_rounds
        loop = LoopBlock(
            block_id="review_loop",
            inner_block_refs=["writer", "gate"],
            max_rounds=2,
        )

        wf = Workflow(name="gate_in_loop_no_exit_control")
        wf.add_block(writer)
        wf.add_block(gate)
        wf.add_block(loop)
        wf.set_entry("review_loop")
        wf.add_transition("review_loop", None)

        state = _fresh_state(
            current_task=Task(id="t1", instruction="Write and review", context="test"),
        )

        final = await wf.run(state)

        loop_meta = final.shared_memory.get("__loop__review_loop", {})
        assert loop_meta.get("rounds_completed") == 2, (
            "Loop should run all max_rounds when no break_on_exit/retry_on_exit"
        )
        assert loop_meta.get("break_reason") == "max_rounds reached"


# ==============================================================================
# AC5: output_conditions -> exit_handle -> conditional_transitions chain
# ==============================================================================


class TestOutputConditionsExitHandleChainE2E:
    """AC5: Code/linear block with output_conditions computes exit_handle,
    which feeds into conditional_transitions for routing."""

    @pytest.mark.asyncio
    async def test_output_conditions_match_routes_correctly(self):
        """Block produces JSON output -> output_conditions match a case ->
        exit_handle set -> conditional_transition routes to correct block."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="oc_chain")

        producer = JsonOutputBlock("producer", {"status": "approved", "score": 85})
        on_approved = StubBlock("on_approved", output="approved_path")
        on_rejected = StubBlock("on_rejected", output="rejected_path")

        wf.add_block(producer)
        wf.add_block(on_approved)
        wf.add_block(on_rejected)
        wf.set_entry("producer")

        # output_conditions: if status == "approved" -> case_id "approved"
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="rejected")

        wf.add_conditional_transition(
            "producer",
            {"approved": "on_approved", "rejected": "on_rejected", "default": "on_rejected"},
        )
        wf.add_transition("on_approved", None)
        wf.add_transition("on_rejected", None)

        final = await wf.run(_fresh_state())

        # output_conditions should match "approved" and set exit_handle
        assert final.results["producer"].exit_handle == "approved"
        assert "on_approved" in final.results, (
            "Should route to on_approved via output_conditions -> exit_handle -> conditional_transition"
        )
        assert "on_rejected" not in final.results

    @pytest.mark.asyncio
    async def test_output_conditions_no_match_uses_default(self):
        """Block output doesn't match any case -> default decision used ->
        exit_handle set to default -> routes to fallback block."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="oc_default_chain")

        producer = JsonOutputBlock("producer", {"status": "pending", "score": 50})
        on_approved = StubBlock("on_approved", output="approved_path")
        on_fallback = StubBlock("on_fallback", output="fallback_path")

        wf.add_block(producer)
        wf.add_block(on_approved)
        wf.add_block(on_fallback)
        wf.set_entry("producer")

        # output_conditions: if status == "approved" -> case_id "approved"
        # No case for "pending" -> falls to default="rejected"
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="rejected")

        wf.add_conditional_transition(
            "producer",
            {"approved": "on_approved", "rejected": "on_fallback", "default": "on_fallback"},
        )
        wf.add_transition("on_approved", None)
        wf.add_transition("on_fallback", None)

        final = await wf.run(_fresh_state())

        assert final.results["producer"].exit_handle == "rejected"
        assert "on_fallback" in final.results
        assert "on_approved" not in final.results

    @pytest.mark.asyncio
    async def test_block_with_exit_handle_and_output_conditions(self):
        """When a block already has exit_handle set, output_conditions should
        NOT override it (exit_handle takes priority)."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="exit_handle_priority")

        # This block has exit_handle already set
        producer = ExitHandleBlock(
            "producer", exit_handle="custom_exit", output='{"status": "approved"}'
        )
        on_custom = StubBlock("on_custom", output="custom_path")
        on_approved = StubBlock("on_approved", output="approved_path")

        wf.add_block(producer)
        wf.add_block(on_custom)
        wf.add_block(on_approved)
        wf.set_entry("producer")

        # Even though output_conditions would match "approved",
        # the pre-set exit_handle="custom_exit" should take priority
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="default")

        wf.add_conditional_transition(
            "producer",
            {
                "custom_exit": "on_custom",
                "approved": "on_approved",
                "default": "on_approved",
            },
        )
        wf.add_transition("on_custom", None)
        wf.add_transition("on_approved", None)

        final = await wf.run(_fresh_state())

        assert final.results["producer"].exit_handle == "custom_exit"
        assert "on_custom" in final.results, (
            "exit_handle should take priority over output_conditions"
        )
        assert "on_approved" not in final.results


# ==============================================================================
# AC6: Validation catches all invalid configurations
# ==============================================================================


class TestValidationCatchesInvalidConfigs:
    """AC6: validate() and parse_workflow_yaml() catch invalid exit configurations."""

    def test_transition_key_not_in_declared_exits_fails(self):
        """A transition key that doesn't match declared exits produces a validation error."""
        wf = Workflow(name="bad_exits")

        gate = StubBlock("gate")
        gate._declared_exits = [
            ExitDef(id="pass", label="Pass"),
            ExitDef(id="fail", label="Fail"),
        ]

        wf.add_block(gate)
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_nonexistent"))
        wf.set_entry("gate")

        wf.add_conditional_transition(
            "gate",
            {
                "pass": "on_pass",
                "nonexistent": "on_nonexistent",  # NOT in declared exits
            },
        )

        errors = wf.validate()
        assert len(errors) > 0, "validate() should catch 'nonexistent' not in declared exits"
        assert any("nonexistent" in e for e in errors)

    def test_default_key_always_allowed(self):
        """'default' transition key is always valid even when not in declared exits."""
        wf = Workflow(name="default_allowed")

        gate = StubBlock("gate")
        gate._declared_exits = [
            ExitDef(id="pass", label="Pass"),
            ExitDef(id="fail", label="Fail"),
        ]

        wf.add_block(gate)
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_default"))
        wf.set_entry("gate")

        wf.add_conditional_transition(
            "gate",
            {
                "pass": "on_pass",
                "default": "on_default",  # Always valid
            },
        )
        wf.add_transition("on_pass", None)
        wf.add_transition("on_default", None)

        errors = wf.validate()
        assert len(errors) == 0, f"'default' should always be allowed. Got: {errors}"

    def test_yaml_with_bad_transition_key_fails_parse(self):
        """Parsing a YAML workflow with a transition key not in declared exits
        should raise ValueError."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_bad_key
  entry: gate
  transitions: []
  conditional_transitions:
    - from: gate
      nonexistent_key: on_approved
      default: on_rejected

souls:
  test_soul:
    id: test_soul
    role: Test
    system_prompt: "test"

blocks:
  gate:
    type: gate
    soul_ref: test_soul
    eval_key: content
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  on_approved:
    type: linear
    soul_ref: test_soul
  on_rejected:
    type: linear
    soul_ref: test_soul
"""
        with pytest.raises(ValueError, match="nonexistent_key"):
            parse_workflow_yaml(yaml_content)

    def test_yaml_with_valid_exits_parses_ok(self):
        """YAML with correct exit declarations and matching transition keys
        should parse without errors."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_valid_exits
  entry: gate
  transitions: []
  conditional_transitions:
    - from: gate
      pass: on_pass
      fail: on_fail
      default: on_fail

souls:
  test_soul:
    id: test_soul
    role: Test
    system_prompt: "test"

blocks:
  gate:
    type: gate
    soul_ref: test_soul
    eval_key: content
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  on_pass:
    type: linear
    soul_ref: test_soul
  on_fail:
    type: linear
    soul_ref: test_soul
"""
        wf = parse_workflow_yaml(yaml_content)
        assert wf is not None
        assert wf.name == "test_valid_exits"

    def test_yaml_gate_auto_injects_exits_then_validates(self):
        """Gate blocks auto-inject pass/fail exits during build(). A YAML workflow
        with a gate + conditional_transitions using pass/fail should parse cleanly."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_gate_auto_exits
  entry: gate
  transitions: []
  conditional_transitions:
    - from: gate
      pass: on_pass
      fail: on_fail
      default: on_fail

souls:
  test_soul:
    id: test_soul
    role: Test
    system_prompt: "test"

blocks:
  gate:
    type: gate
    soul_ref: test_soul
    eval_key: content
  on_pass:
    type: linear
    soul_ref: test_soul
  on_fail:
    type: linear
    soul_ref: test_soul
"""
        # Gate without explicit exits should have pass/fail auto-injected
        wf = parse_workflow_yaml(yaml_content)
        assert wf is not None

        # The gate's _declared_exits should have been set by build()
        gate_block = wf.blocks["gate"]
        declared = getattr(gate_block, "_declared_exits", None)
        assert declared is not None, (
            "Gate block should have _declared_exits auto-injected by build()"
        )
        exit_ids = {e.id for e in declared}
        assert "pass" in exit_ids
        assert "fail" in exit_ids


# ==============================================================================
# Full workflow execution with branching via exit ports (from YAML)
# ==============================================================================


class TestFullWorkflowBranchingFromYAML:
    """Full integration: parse a YAML workflow that uses exit ports, then run it."""

    @pytest.mark.asyncio
    async def test_full_yaml_gate_workflow_pass_path(self):
        """Parse a complete YAML workflow with gate + conditional_transitions,
        mock the runner to PASS, verify correct execution path."""
        from unittest.mock import patch

        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_gate_e2e
  entry: content_block
  transitions:
    - from: content_block
      to: quality_gate
  conditional_transitions:
    - from: quality_gate
      pass: publish
      fail: revise
      default: revise

souls:
  writer:
    id: writer
    role: Writer
    system_prompt: "Write content"
    provider: openai
    model_name: gpt-4o
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: "Evaluate quality. Respond PASS or FAIL: reason"
    provider: openai
    model_name: gpt-4o

blocks:
  content_block:
    type: linear
    soul_ref: writer
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: content_block
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  publish:
    type: linear
    soul_ref: writer
  revise:
    type: linear
    soul_ref: writer
"""
        wf = parse_workflow_yaml(yaml_content)

        # Mock the LLM to return predictable outputs
        with patch("runsight_core.runner.LiteLLMClient.achat") as mock_achat:
            call_count = {"n": 0}

            async def _side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # content_block output
                    return {
                        "content": "Great article about AI agents.",
                        "cost_usd": 0.01,
                        "total_tokens": 50,
                    }
                elif call_count["n"] == 2:
                    # quality_gate evaluation -> PASS
                    return {
                        "content": "PASS",
                        "cost_usd": 0.01,
                        "total_tokens": 30,
                    }
                else:
                    # publish block
                    return {
                        "content": "Published successfully.",
                        "cost_usd": 0.01,
                        "total_tokens": 20,
                    }

            mock_achat.side_effect = _side_effect

            state = WorkflowState(
                current_task=Task(
                    id="test_task",
                    instruction="Write and publish an article",
                    context="About AI agents",
                ),
            )

            final = await wf.run(state)

        # Verify the correct execution path: content_block -> gate (PASS) -> publish
        assert "content_block" in final.results
        assert "quality_gate" in final.results
        assert final.results["quality_gate"].exit_handle == "pass"
        assert "publish" in final.results, (
            "Gate PASS should route to 'publish' block via conditional_transition"
        )
        assert "revise" not in final.results, "Gate PASS should NOT route to 'revise' block"

    @pytest.mark.asyncio
    async def test_full_yaml_gate_workflow_fail_path(self):
        """Parse a complete YAML workflow, mock runner to FAIL, verify fail path."""
        from unittest.mock import patch

        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_gate_fail_e2e
  entry: content_block
  transitions:
    - from: content_block
      to: quality_gate
  conditional_transitions:
    - from: quality_gate
      pass: publish
      fail: revise
      default: revise

souls:
  writer:
    id: writer
    role: Writer
    system_prompt: "Write content"
    provider: openai
    model_name: gpt-4o
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: "Evaluate quality. Respond PASS or FAIL: reason"
    provider: openai
    model_name: gpt-4o

blocks:
  content_block:
    type: linear
    soul_ref: writer
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: content_block
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  publish:
    type: linear
    soul_ref: writer
  revise:
    type: linear
    soul_ref: writer
"""
        wf = parse_workflow_yaml(yaml_content)

        with patch("runsight_core.runner.LiteLLMClient.achat") as mock_achat:
            call_count = {"n": 0}

            async def _side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return {
                        "content": "Rough draft about AI.",
                        "cost_usd": 0.01,
                        "total_tokens": 50,
                    }
                elif call_count["n"] == 2:
                    # quality_gate -> FAIL
                    return {
                        "content": "FAIL: needs more detail",
                        "cost_usd": 0.01,
                        "total_tokens": 30,
                    }
                else:
                    # revise block
                    return {
                        "content": "Revised with more detail.",
                        "cost_usd": 0.01,
                        "total_tokens": 40,
                    }

            mock_achat.side_effect = _side_effect

            state = WorkflowState(
                current_task=Task(
                    id="test_task",
                    instruction="Write article",
                    context="About AI",
                ),
            )

            final = await wf.run(state)

        assert "content_block" in final.results
        assert "quality_gate" in final.results
        assert final.results["quality_gate"].exit_handle == "fail"
        assert "revise" in final.results, (
            "Gate FAIL should route to 'revise' block via conditional_transition"
        )
        assert "publish" not in final.results, "Gate FAIL should NOT route to 'publish' block"


# ==============================================================================
# YAML round-trip: exit port declarations survive parse -> dump -> parse
# ==============================================================================


class TestYamlExitPortRoundTrip:
    """Exit port declarations in YAML survive a parse -> model_dump -> re-parse cycle."""

    def test_gate_exits_survive_schema_round_trip(self):
        """Parse a YAML with gate exits, dump to dict, verify exits are present."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_content = """
version: "1.0"

config:
  model_name: gpt-4o

souls:
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: "Evaluate quality"

blocks:
  gate:
    type: gate
    soul_ref: reviewer
    eval_key: content
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail

workflow:
  name: roundtrip_test
  entry: gate
  transitions:
    - from: gate
      to: null
"""
        data = yaml.safe_load(yaml_content)

        # Trigger block type registration
        import runsight_core.blocks  # noqa: F401
        from runsight_core.yaml.schema import rebuild_block_def_union

        rebuild_block_def_union()

        file_def = RunsightWorkflowFile.model_validate(data)
        gate_def = file_def.blocks["gate"]

        assert gate_def.exits is not None, "Exits should parse from YAML"
        assert len(gate_def.exits) == 2
        exit_ids = [e.id for e in gate_def.exits]
        assert "pass" in exit_ids
        assert "fail" in exit_ids

    def test_loop_break_on_exit_survives_schema_round_trip(self):
        """Parse a YAML with loop break_on_exit, dump, verify field is present."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_content = """
version: "1.0"

config:
  model_name: gpt-4o

souls:
  writer:
    id: writer
    role: Writer
    system_prompt: "Write content"
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: "Evaluate quality"

blocks:
  writer:
    type: linear
    soul_ref: writer
  gate:
    type: gate
    soul_ref: reviewer
    eval_key: writer
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  review_loop:
    type: loop
    inner_block_refs:
      - writer
      - gate
    max_rounds: 3
    break_on_exit: pass
    retry_on_exit: fail

workflow:
  name: loop_exit_roundtrip
  entry: review_loop
  transitions:
    - from: review_loop
      to: null
"""
        data = yaml.safe_load(yaml_content)

        import runsight_core.blocks  # noqa: F401
        from runsight_core.yaml.schema import rebuild_block_def_union

        rebuild_block_def_union()

        file_def = RunsightWorkflowFile.model_validate(data)
        loop_def = file_def.blocks["review_loop"]

        assert loop_def.break_on_exit == "pass", "break_on_exit should survive YAML -> schema parse"
        assert loop_def.retry_on_exit == "fail", "retry_on_exit should survive YAML -> schema parse"


# ==============================================================================
# External soul file resolution via _discover_external_souls
# ==============================================================================


class TestExternalSoulFileResolution:
    """parse_workflow_yaml resolves soul_refs from files in custom/souls/."""

    def test_external_soul_file_resolves_for_linear_block(self, tmp_path):
        """A workflow YAML with no inline souls resolves soul_ref from a file in tmp/custom/souls/."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        souls_dir = tmp_path / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "narrator.yaml").write_text(
            "id: narrator\nrole: Narrator\nsystem_prompt: Tell the story.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )

        yaml_content = """
workflow:
  name: external_soul_linear
  entry: story_block
  transitions:
    - from: story_block
      to: null

blocks:
  story_block:
    type: linear
    soul_ref: narrator
"""
        wf = parse_workflow_yaml(yaml_content, _base_dir=str(tmp_path))
        assert wf is not None
        assert wf.name == "external_soul_linear"
        assert "story_block" in wf.blocks

    def test_external_soul_file_resolves_for_gate_block(self, tmp_path):
        """A gate workflow YAML with no inline souls resolves soul_refs from tmp/custom/souls/."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        souls_dir = tmp_path / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "author.yaml").write_text(
            "id: author\nrole: Author\nsystem_prompt: Write content.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )
        (souls_dir / "judge.yaml").write_text(
            "id: judge\nrole: Judge\nsystem_prompt: Evaluate content. Respond PASS or FAIL.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )

        yaml_content = """
workflow:
  name: external_soul_gate
  entry: draft
  transitions:
    - from: draft
      to: quality_check
  conditional_transitions:
    - from: quality_check
      pass: done
      fail: done
      default: done

blocks:
  draft:
    type: linear
    soul_ref: author
  quality_check:
    type: gate
    soul_ref: judge
    eval_key: draft
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  done:
    type: linear
    soul_ref: author
"""
        wf = parse_workflow_yaml(yaml_content, _base_dir=str(tmp_path))
        assert wf is not None
        assert wf.name == "external_soul_gate"
        gate = wf.blocks["quality_check"]
        declared_ids = {e.id for e in gate._declared_exits}
        assert "pass" in declared_ids
        assert "fail" in declared_ids
