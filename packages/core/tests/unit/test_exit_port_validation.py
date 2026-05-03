"""Exit-port validation coverage."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import ExitDef

# ---------------------------------------------------------------------------
# Helpers: mock runner and blocks
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(id=soul_id, kind="soul", name="Test", role="Test", system_prompt="Test prompt")


class StubBlock(BaseBlock):
    """Minimal block that stores a fixed output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block whose execute() stores a BlockResult with a specific exit_handle."""

    def __init__(self, block_id: str, exit_handle: str, output: str = "done"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
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
        return block_output_from_state(self.block_id, state, next_state)


class JsonOutputBlock(BaseBlock):
    """Block that stores a JSON-string BlockResult (no exit_handle set)."""

    def __init__(self, block_id: str, data: dict):
        super().__init__(block_id)
        self._data = data

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._data)),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


def _fresh_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


class TestValidationCatchesInvalidConfigs:
    """validate() and parse_workflow_yaml() catch invalid exit configurations."""

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
                "nonexistent": "on_nonexistent",  # outside declared exits
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
id: test-workflow
kind: workflow
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
    kind: soul
    name: Test
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
id: test-workflow
kind: workflow
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
    kind: soul
    name: Test
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
id: test-workflow
kind: workflow
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
    kind: soul
    name: Test
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
