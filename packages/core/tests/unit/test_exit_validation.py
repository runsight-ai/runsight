"""
Tests for generic exit validation in Workflow.validate().

These tests cover the current behavior:
- validate() catches mismatched transition keys vs declared exits
- validate() allows "default" as a transition key always
- validate() skips exit checks for blocks without declared exits
- parser stores _declared_exits on runtime blocks after building
"""

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import ExitDef


class StubBlock(BaseBlock):
    """Minimal block for unit-testing validate() without executing runtime logic."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state  # pragma: no cover


class StubBlockWithExits(BaseBlock):
    """Block with _declared_exits for testing conditional transition validation."""

    def __init__(self, block_id: str, exits: list[ExitDef]):
        super().__init__(block_id)
        self._declared_exits = exits

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state  # pragma: no cover


class TestValidateExitMismatch:
    """validate() detects transition keys that do not match declared exits."""

    def test_mismatched_transition_key_produces_error(self):
        wf = Workflow(name="exit_mismatch")

        block_with_exits = StubBlockWithExits(
            "decision",
            exits=[
                ExitDef(id="approved", label="Approved"),
                ExitDef(id="rejected", label="Rejected"),
            ],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("on_approved"))
        wf.add_block(StubBlock("on_rejected"))
        wf.add_block(StubBlock("on_nonexistent"))
        wf.set_entry("decision")
        wf.add_conditional_transition(
            "decision",
            {
                "approved": "on_approved",
                "rejected": "on_rejected",
                "nonexistent": "on_nonexistent",
            },
        )

        errors = wf.validate()
        assert len(errors) > 0
        assert any("nonexistent" in e for e in errors)

    def test_multiple_mismatched_keys_produce_multiple_errors(self):
        wf = Workflow(name="multi_mismatch")

        block_with_exits = StubBlockWithExits(
            "gate",
            exits=[ExitDef(id="pass", label="Pass")],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("on_pass"))
        wf.add_block(StubBlock("on_fail"))
        wf.add_block(StubBlock("on_error"))
        wf.set_entry("gate")
        wf.add_conditional_transition(
            "gate",
            {
                "pass": "on_pass",
                "fail": "on_fail",
                "error": "on_error",
            },
        )

        errors = wf.validate()
        mismatch_errors = [
            e for e in errors if "transition key" in e.lower() or "not in declared" in e.lower()
        ]
        assert len(mismatch_errors) >= 2

    def test_all_declared_exits_valid_no_errors(self):
        wf = Workflow(name="valid_exits")

        block_with_exits = StubBlockWithExits(
            "decision",
            exits=[
                ExitDef(id="approved", label="Approved"),
                ExitDef(id="rejected", label="Rejected"),
            ],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("on_approved"))
        wf.add_block(StubBlock("on_rejected"))
        wf.set_entry("decision")
        wf.add_conditional_transition(
            "decision",
            {
                "approved": "on_approved",
                "rejected": "on_rejected",
            },
        )

        assert wf.validate() == []


class TestValidateSkipsBlocksWithoutExits:
    """Blocks without declared exits skip the exit-key validation path."""

    def test_block_without_declared_exits_skips_check(self):
        wf = Workflow(name="no_exits")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("branch_a"))
        wf.add_block(StubBlock("branch_b"))
        wf.set_entry("step")
        wf.add_conditional_transition(
            "step",
            {
                "arbitrary_key": "branch_a",
                "another_key": "branch_b",
                "default": "branch_a",
            },
        )

        assert wf.validate() == []

    def test_block_with_declared_exits_none_skips_check(self):
        wf = Workflow(name="exits_none")

        block = StubBlock("step")
        block._declared_exits = None

        wf.add_block(block)
        wf.add_block(StubBlock("target"))
        wf.set_entry("step")
        wf.add_conditional_transition(
            "step",
            {"any_key": "target", "default": "target"},
        )

        assert wf.validate() == []


class TestDefaultAlwaysAllowed:
    """The default transition key remains valid even without an explicit exit."""

    def test_default_key_allowed_even_without_exit_def(self):
        wf = Workflow(name="default_allowed")

        block_with_exits = StubBlockWithExits(
            "decision",
            exits=[
                ExitDef(id="approved", label="Approved"),
                ExitDef(id="rejected", label="Rejected"),
            ],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("on_approved"))
        wf.add_block(StubBlock("on_rejected"))
        wf.add_block(StubBlock("on_default"))
        wf.set_entry("decision")
        wf.add_conditional_transition(
            "decision",
            {
                "approved": "on_approved",
                "rejected": "on_rejected",
                "default": "on_default",
            },
        )

        assert wf.validate() == []

    def test_default_key_alone_with_exits_is_valid(self):
        wf = Workflow(name="default_only")

        block_with_exits = StubBlockWithExits(
            "step",
            exits=[ExitDef(id="done", label="Done")],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("fallback"))
        wf.set_entry("step")
        wf.add_conditional_transition("step", {"default": "fallback"})

        assert wf.validate() == []


class TestConditionalWorkflowsWithoutExits:
    """Existing conditional workflows without declared exits continue to validate."""

    def test_plain_workflow_no_exits_validates(self):
        wf = Workflow(name="simple")

        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.add_transition("a", "b")
        wf.add_transition("b", None)
        wf.set_entry("a")

        assert wf.validate() == []

    def test_conditional_workflow_no_exits_validates(self):
        wf = Workflow(name="conditional_no_exits")

        wf.add_block(StubBlock("decision"))
        wf.add_block(StubBlock("branch_a"))
        wf.add_block(StubBlock("branch_b"))
        wf.set_entry("decision")
        wf.add_conditional_transition(
            "decision",
            {
                "choice_a": "branch_a",
                "choice_b": "branch_b",
                "default": "branch_a",
            },
        )

        assert wf.validate() == []


class TestParserStoresDeclaredExits:
    """Parser stores declared exits on runtime blocks for validation."""

    def test_parsed_block_has_declared_exits_attribute(self):
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
id: test_exits_stored
kind: workflow
workflow:
  id: test_exits_stored
  kind: workflow
  name: test_exits_stored
  entry: decision
  transitions: []
  conditional_transitions:
    - from: decision
      approved: on_approved
      rejected: on_rejected
      default: on_rejected

souls:
  test_soul:
    id: test_soul
    kind: soul
    name: Test
    role: Test
    system_prompt: "test"

blocks:
  decision:
    type: linear
    soul_ref: test_soul
    exits:
      - id: approved
        label: Approved
      - id: rejected
        label: Rejected
  on_approved:
    type: linear
    soul_ref: test_soul
  on_rejected:
    type: linear
    soul_ref: test_soul
"""
        wf = parse_workflow_yaml(yaml_content)
        decision_block = wf.blocks["decision"]
        assert hasattr(decision_block, "_declared_exits")
