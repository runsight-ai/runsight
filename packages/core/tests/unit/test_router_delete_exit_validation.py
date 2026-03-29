"""
Failing tests for RUN-270: Delete RouterBlock, add exit validation to validate().

After this ticket:
- router.py is deleted — `type: router` in YAML raises a parse error
- "router" is not in block registries
- Importing RouterBlock fails (ImportError)
- validate() catches mismatched transition keys vs declared exits
- validate() allows "default" as a transition key always
- validate() skips exit check for blocks without declared exits
- Parser stores _declared_exits on runtime blocks after building

Tests cover:
- AC1: RouterBlock deleted — `type: router` in YAML raises parse error
- AC2: validate() catches mismatched transition keys vs declared exits
- AC3: validate() skips check for blocks without declared exits
- AC4: "default" is always allowed as a transition key
- AC5: Existing YAML without exits: validation passes (no exits = no check)
"""

import os

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import ExitDef

# ---------------------------------------------------------------------------
# Stub block for validate() tests (never executed)
# ---------------------------------------------------------------------------


class StubBlock(BaseBlock):
    """Minimal block for unit-testing validate() — never actually executed."""

    def __init__(self, block_id: str):
        super().__init__(block_id)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state  # pragma: no cover


class StubBlockWithExits(BaseBlock):
    """Block with _declared_exits for testing exit validation."""

    def __init__(self, block_id: str, exits: list[ExitDef]):
        super().__init__(block_id)
        self._declared_exits = exits

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state  # pragma: no cover


# ==============================================================================
# AC1: RouterBlock deleted — type: router in YAML raises parse error
# ==============================================================================


class TestRouterBlockDeleted:
    """AC1: router.py is deleted, `type: router` is no longer available."""

    def test_router_py_file_does_not_exist(self):
        """The file router.py must be deleted from the blocks directory."""
        router_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "src",
            "runsight_core",
            "blocks",
            "router.py",
        )
        router_path = os.path.normpath(router_path)
        assert not os.path.exists(router_path), (
            f"router.py still exists at {router_path} — it must be deleted"
        )

    def test_router_not_in_block_def_registry(self):
        """'router' must not be in the BLOCK_DEF_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert "router" not in BLOCK_DEF_REGISTRY, (
            "'router' is still registered in BLOCK_DEF_REGISTRY — "
            "deleting router.py should remove it from auto-discovery"
        )

    def test_router_not_in_block_builder_registry(self):
        """'router' must not be in the BLOCK_BUILDER_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert "router" not in BLOCK_BUILDER_REGISTRY, (
            "'router' is still registered in BLOCK_BUILDER_REGISTRY — "
            "deleting router.py should remove it from auto-discovery"
        )

    def test_importing_router_block_fails(self):
        """Importing RouterBlock from the deleted module must raise ImportError."""
        with pytest.raises(ImportError):
            from runsight_core.blocks.router import RouterBlock  # noqa: F401

    def test_type_router_yaml_raises_parse_error(self):
        """Parsing a YAML workflow with `type: router` must raise an error
        (ValidationError or ValueError) since the block type no longer exists."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_router_deleted
  entry: my_router
  transitions:
    - from: my_router
      to: null

souls:
  test_soul:
    id: test_soul_1
    role: Test
    system_prompt: "test"

blocks:
  my_router:
    type: router
    soul_ref: test_soul
"""
        with pytest.raises((Exception,)):
            # Should fail at schema validation or builder lookup — router type is gone
            parse_workflow_yaml(yaml_content)


# ==============================================================================
# AC2: validate() catches mismatched transition keys vs declared exits
# ==============================================================================


class TestValidateExitMismatch:
    """AC2: validate() must detect transition keys that don't match declared exits."""

    def test_mismatched_transition_key_produces_error(self):
        """A transition key 'nonexistent' not in declared exits should produce
        a validation error."""
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

        # "nonexistent" is NOT in declared exits {approved, rejected, default}
        wf.add_conditional_transition(
            "decision",
            {
                "approved": "on_approved",
                "rejected": "on_rejected",
                "nonexistent": "on_nonexistent",
            },
        )

        errors = wf.validate()
        assert len(errors) > 0, "validate() should catch mismatched transition key 'nonexistent'"
        assert any("nonexistent" in e for e in errors), (
            f"Error should mention 'nonexistent' key. Got: {errors}"
        )

    def test_multiple_mismatched_keys_produce_multiple_errors(self):
        """Multiple invalid transition keys should each produce an error."""
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

        # "fail" and "error" are NOT in declared exits {pass, default}
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
        assert len(mismatch_errors) >= 2, (
            f"Expected at least 2 mismatch errors (for 'fail' and 'error'). Got: {errors}"
        )

    def test_all_declared_exits_valid_no_errors(self):
        """When all transition keys match declared exits, no errors should be produced."""
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

        errors = wf.validate()
        assert len(errors) == 0, f"Expected no errors for valid exits. Got: {errors}"


# ==============================================================================
# AC3: validate() skips check for blocks without declared exits
# ==============================================================================


class TestValidateSkipsBlocksWithoutExits:
    """AC3: validate() must skip exit validation for blocks that don't have
    _declared_exits (i.e., regular blocks without exits defined)."""

    def test_block_without_declared_exits_skips_check(self):
        """A regular StubBlock (no _declared_exits) with conditional transitions
        should pass validation — no exit mismatch check is performed."""
        wf = Workflow(name="no_exits")

        wf.add_block(StubBlock("step"))
        wf.add_block(StubBlock("branch_a"))
        wf.add_block(StubBlock("branch_b"))
        wf.set_entry("step")

        # Arbitrary transition keys — no _declared_exits means no check
        wf.add_conditional_transition(
            "step",
            {
                "arbitrary_key": "branch_a",
                "another_key": "branch_b",
                "default": "branch_a",
            },
        )

        errors = wf.validate()
        assert len(errors) == 0, (
            f"Block without _declared_exits should not trigger exit validation. Got: {errors}"
        )

    def test_block_with_declared_exits_none_skips_check(self):
        """A block where _declared_exits is explicitly None should skip the check."""
        wf = Workflow(name="exits_none")

        block = StubBlock("step")
        block._declared_exits = None  # Explicitly set to None

        wf.add_block(block)
        wf.add_block(StubBlock("target"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"any_key": "target", "default": "target"},
        )

        errors = wf.validate()
        assert len(errors) == 0, (
            f"Block with _declared_exits=None should skip exit check. Got: {errors}"
        )


# ==============================================================================
# AC4: "default" is always allowed as a transition key
# ==============================================================================


class TestDefaultAlwaysAllowed:
    """AC4: 'default' is implicitly allowed in transition keys even if not
    in the block's declared exits list."""

    def test_default_key_allowed_even_without_exit_def(self):
        """'default' transition key is always valid, even if the block's
        declared exits don't include an exit with id='default'."""
        wf = Workflow(name="default_allowed")

        block_with_exits = StubBlockWithExits(
            "decision",
            exits=[
                ExitDef(id="approved", label="Approved"),
                ExitDef(id="rejected", label="Rejected"),
                # No explicit "default" exit — but "default" must still be allowed
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
                "default": "on_default",  # Always valid
            },
        )

        errors = wf.validate()
        assert len(errors) == 0, (
            f"'default' should always be allowed as a transition key. Got: {errors}"
        )

    def test_default_key_alone_with_exits_is_valid(self):
        """A block with declared exits and only a 'default' transition key
        should pass validation."""
        wf = Workflow(name="default_only")

        block_with_exits = StubBlockWithExits(
            "step",
            exits=[ExitDef(id="done", label="Done")],
        )

        wf.add_block(block_with_exits)
        wf.add_block(StubBlock("fallback"))
        wf.set_entry("step")

        wf.add_conditional_transition(
            "step",
            {"default": "fallback"},
        )

        errors = wf.validate()
        assert len(errors) == 0, f"'default' alone should be valid. Got: {errors}"


# ==============================================================================
# AC5: Existing YAML without exits: validation passes (no exits = no check)
# ==============================================================================


class TestExistingYamlWithoutExitsStillValid:
    """AC5: Workflows defined without exits on blocks continue to work —
    the new exit validation only fires when _declared_exits is present."""

    def test_plain_workflow_no_exits_validates(self):
        """A simple A -> B workflow with no exits on any block should
        pass validation without errors."""
        wf = Workflow(name="simple")

        wf.add_block(StubBlock("a"))
        wf.add_block(StubBlock("b"))
        wf.add_transition("a", "b")
        wf.add_transition("b", None)
        wf.set_entry("a")

        errors = wf.validate()
        assert len(errors) == 0, f"Plain workflow should validate. Got: {errors}"

    def test_conditional_workflow_no_exits_validates(self):
        """A conditional workflow where blocks have no exits defined should
        pass validation — no exit mismatch check fires."""
        wf = Workflow(name="conditional_no_exits")

        wf.add_block(StubBlock("router"))
        wf.add_block(StubBlock("branch_a"))
        wf.add_block(StubBlock("branch_b"))
        wf.set_entry("router")

        wf.add_conditional_transition(
            "router",
            {
                "choice_a": "branch_a",
                "choice_b": "branch_b",
                "default": "branch_a",
            },
        )

        errors = wf.validate()
        assert len(errors) == 0, (
            f"Conditional workflow without exits should validate. Got: {errors}"
        )


# ==============================================================================
# Parser: _declared_exits stored on runtime blocks
# ==============================================================================


class TestParserStoresDeclaredExits:
    """Parser must store block_def.exits as _declared_exits on the runtime block
    so validate() can access them."""

    def test_parsed_block_has_declared_exits_attribute(self):
        """After parsing a workflow with exits defined on a block, the runtime
        block should have _declared_exits set."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
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
    id: test_soul_1
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
        assert hasattr(decision_block, "_declared_exits"), (
            "Parser should store _declared_exits on runtime block"
        )
        assert decision_block._declared_exits is not None, (
            "_declared_exits should not be None when exits are defined in YAML"
        )
        exit_ids = {e.id for e in decision_block._declared_exits}
        assert exit_ids == {"approved", "rejected"}, (
            f"Expected exits {{approved, rejected}}, got {exit_ids}"
        )

    def test_parsed_block_without_exits_has_no_declared_exits(self):
        """A block without exits defined should NOT have _declared_exits set,
        or it should be None."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_no_exits
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null

souls:
  test_soul:
    id: test_soul_1
    role: Test
    system_prompt: "test"

blocks:
  step_a:
    type: linear
    soul_ref: test_soul
  step_b:
    type: linear
    soul_ref: test_soul
"""
        wf = parse_workflow_yaml(yaml_content)
        step_a_block = wf.blocks["step_a"]
        declared = getattr(step_a_block, "_declared_exits", None)
        assert declared is None, (
            f"Block without exits should have _declared_exits=None, got {declared}"
        )


# ==============================================================================
# Integration: validate() + _declared_exits from parser
# ==============================================================================


class TestValidateWithParsedExits:
    """Integration: parser stores _declared_exits, validate() uses them."""

    def test_parsed_workflow_with_mismatched_exits_fails_validation(self):
        """A parsed workflow where transition keys don't match declared exits
        should fail validation during parse_workflow_yaml (which calls validate())."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_mismatch_parsed
  entry: decision
  transitions: []
  conditional_transitions:
    - from: decision
      nonexistent_key: on_approved
      default: on_rejected

souls:
  test_soul:
    id: test_soul_1
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
        with pytest.raises(ValueError, match="nonexistent_key"):
            parse_workflow_yaml(yaml_content)

    def test_parsed_workflow_with_valid_exits_passes_validation(self):
        """A parsed workflow where all transition keys match declared exits
        should pass validation."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test_valid_parsed
  entry: decision
  transitions: []
  conditional_transitions:
    - from: decision
      approved: on_approved
      rejected: on_rejected
      default: on_rejected

souls:
  test_soul:
    id: test_soul_1
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
        # Should NOT raise — all transition keys are in declared exits
        wf = parse_workflow_yaml(yaml_content)
        assert wf is not None
