"""
Tests for RUN-201: Remove PlaceholderBlock from core engine.

Verifies that PlaceholderBlock and PlaceholderBlockDef have been fully removed,
that dynamic injection raises ValueError instead of falling back to PlaceholderBlock,
that YAML with type: placeholder is rejected, and that shared test infrastructure
exists in conftest.py.

These tests are written to FAIL against the current codebase and PASS once
Green Team completes the removal.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.yaml.parser import parse_workflow_yaml


# ---------------------------------------------------------------------------
# Helpers (local to this test file)
# ---------------------------------------------------------------------------


class MockBlock(BaseBlock):
    """Simple test block for workflow execution tests."""

    def __init__(self, block_id: str, output: str = "mock output"):
        super().__init__(block_id)
        self.output = output

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=self.output)},
                "execution_log": state.execution_log
                + [{"role": "system", "content": f"[Block {self.block_id}] Executed"}],
            }
        )


class PlannerBlock(BaseBlock):
    """Block that injects a dynamic step with an unknown step_id."""

    def __init__(self) -> None:
        super().__init__("planner")

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: "plan generated"},
                "metadata": {
                    **state.metadata,
                    "planner_new_steps": [
                        {
                            "step_id": "unregistered_step",
                            "description": "Unknown step type",
                        }
                    ],
                },
                "execution_log": state.execution_log
                + [{"role": "system", "content": "[Block planner] PlannerBlock"}],
            }
        )


# ===========================================================================
# 1. PlaceholderBlock is NOT importable from runsight_core
# ===========================================================================


class TestPlaceholderBlockRemoved:
    """Verify PlaceholderBlock is fully removed from the public API."""

    def test_placeholder_block_not_importable_from_runsight_core(self):
        """PlaceholderBlock must not be importable from the runsight_core package."""
        import runsight_core

        assert not hasattr(runsight_core, "PlaceholderBlock"), (
            "PlaceholderBlock should have been removed from runsight_core.__init__"
        )

    def test_placeholder_block_not_in_runsight_core_all(self):
        """PlaceholderBlock must not appear in runsight_core.__all__."""
        import runsight_core

        assert "PlaceholderBlock" not in runsight_core.__all__, (
            "PlaceholderBlock should have been removed from __all__"
        )

    def test_placeholder_block_not_importable_from_blocks_package(self):
        """PlaceholderBlock must not be importable from blocks package."""
        import runsight_core.blocks as blocks_pkg

        assert not hasattr(blocks_pkg, "PlaceholderBlock"), (
            "PlaceholderBlock class should have been removed from blocks package"
        )


# ===========================================================================
# 2. PlaceholderBlockDef is NOT in the schema's BlockDef union
# ===========================================================================


class TestPlaceholderBlockDefRemoved:
    """Verify PlaceholderBlockDef is fully removed from the YAML schema."""

    def test_placeholder_block_def_not_importable_from_schema(self):
        """PlaceholderBlockDef must not be importable from yaml.schema."""
        from runsight_core.yaml import schema

        assert not hasattr(schema, "PlaceholderBlockDef"), (
            "PlaceholderBlockDef should have been removed from schema.py"
        )

    def test_placeholder_type_not_in_block_def_union(self):
        """type: placeholder must not be accepted by the BlockDef discriminated union."""
        from runsight_core.yaml.schema import BlockDef

        adapter = TypeAdapter(BlockDef)
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "placeholder"})

    def test_placeholder_type_with_description_not_in_block_def_union(self):
        """type: placeholder with description must not be accepted by BlockDef."""
        from runsight_core.yaml.schema import BlockDef

        adapter = TypeAdapter(BlockDef)
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "placeholder", "description": "test"})


# ===========================================================================
# 3. "placeholder" is NOT in BLOCK_TYPE_REGISTRY
# ===========================================================================


class TestPlaceholderNotInRegistry:
    """Verify placeholder is removed from the parser's block type registry."""

    def test_placeholder_not_in_block_type_registry(self):
        """The string 'placeholder' must not be a key in BLOCK_TYPE_REGISTRY."""
        assert "placeholder" not in BLOCK_TYPE_REGISTRY, (
            "'placeholder' should have been removed from BLOCK_TYPE_REGISTRY"
        )

    def test_block_type_registry_count_decreased(self):
        """BLOCK_TYPE_REGISTRY should have 7 entries (after removing router, placeholder, http_request, file_writer, team_lead, and engineering_manager)."""
        assert len(BLOCK_TYPE_REGISTRY) == 7, (
            f"Expected 7 block types after removing router+placeholder+http_request+file_writer+team_lead+engineering_manager, got {len(BLOCK_TYPE_REGISTRY)}"
        )


# ===========================================================================
# 4. Dynamic injection raises ValueError for unregistered step types
# ===========================================================================


class TestDynamicInjectionRaisesValueError:
    """Dynamic injection must raise ValueError when registry misses a step,
    instead of falling back to PlaceholderBlock."""

    @pytest.mark.asyncio
    async def test_injection_no_registry_raises_value_error(self):
        """When registry is None, injecting a step must raise ValueError."""
        terminal_block = MockBlock("terminal", "Terminal output")

        wf = Workflow(name="injection_test")
        wf.add_block(PlannerBlock())
        wf.add_block(terminal_block)
        wf.add_transition("planner", "terminal")
        wf.add_transition("terminal", None)
        wf.set_entry("planner")

        state = WorkflowState()

        with pytest.raises(ValueError, match="No factory registered"):
            await wf.run(state, registry=None)

    @pytest.mark.asyncio
    async def test_injection_registry_miss_raises_value_error(self):
        """When registry exists but step_id not found, must raise ValueError."""
        from runsight_core.blocks.registry import BlockRegistry

        terminal_block = MockBlock("terminal", "Terminal output")
        registry = BlockRegistry()
        # Registry exists but has no entry for "unregistered_step"

        wf = Workflow(name="injection_test")
        wf.add_block(PlannerBlock())
        wf.add_block(terminal_block)
        wf.add_transition("planner", "terminal")
        wf.add_transition("terminal", None)
        wf.set_entry("planner")

        state = WorkflowState()

        with pytest.raises(ValueError, match="No factory registered"):
            await wf.run(state, registry=registry)


# ===========================================================================
# 5. Parsing YAML with type: placeholder raises a validation error
# ===========================================================================


class TestPlaceholderYamlRejected:
    """YAML documents that use type: placeholder must be rejected."""

    def test_parse_yaml_with_placeholder_block_raises(self):
        """parse_workflow_yaml must reject YAML containing a placeholder block."""
        yaml_content = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  my_block:
    type: placeholder
    description: "This should not work"
workflow:
  name: test_placeholder_rejected
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""
        with pytest.raises((ValidationError, ValueError)):
            parse_workflow_yaml(yaml_content)

    def test_parse_yaml_with_placeholder_block_no_description_raises(self):
        """parse_workflow_yaml must reject YAML containing a placeholder block
        even without a description field."""
        yaml_content = """\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
  my_block:
    type: placeholder
workflow:
  name: test_placeholder_rejected
  entry: my_block
  transitions:
    - from: my_block
      to: null
"""
        with pytest.raises((ValidationError, ValueError)):
            parse_workflow_yaml(yaml_content)


# ===========================================================================
# 6. Test infrastructure exists in conftest.py
# ===========================================================================


class TestConfTestInfrastructure:
    """Verify that shared test infrastructure has been added to conftest.py."""

    def test_make_test_yaml_helper_exists(self):
        """conftest.py must export a make_test_yaml() helper function."""
        # Import from conftest (pytest makes it available as a module in tests/)
        try:
            from conftest import make_test_yaml
        except ImportError:
            pytest.fail("make_test_yaml must be defined in libs/core/tests/conftest.py")

        assert callable(make_test_yaml)

    def test_make_test_yaml_produces_valid_yaml_with_soul(self):
        """make_test_yaml() must wrap step YAML with a valid souls section
        containing a 'test' soul definition, so that parse_workflow_yaml succeeds."""
        from conftest import make_test_yaml

        steps_yaml = """\
  my_block:
    type: linear
    soul_ref: test
"""
        full_yaml = make_test_yaml(steps_yaml)

        # Must be parseable without ValidationError about missing soul
        workflow = parse_workflow_yaml(full_yaml)
        assert isinstance(workflow, Workflow)

    def test_make_test_yaml_includes_test_soul(self):
        """make_test_yaml() output must contain a 'test' soul definition."""
        from conftest import make_test_yaml

        full_yaml = make_test_yaml("""\
  my_block:
    type: linear
    soul_ref: test
""")
        # The YAML must contain "test:" under souls
        assert "test:" in full_yaml

    def test_test_souls_map_fixture_exists(self, test_souls_map):
        """conftest.py must provide a test_souls_map fixture with a 'test' Soul."""
        from runsight_core.primitives import Soul

        assert "test" in test_souls_map
        assert isinstance(test_souls_map["test"], Soul)

    def test_test_souls_map_fixture_soul_has_required_fields(self, test_souls_map):
        """The 'test' Soul in test_souls_map must have id, role, and system_prompt."""
        soul = test_souls_map["test"]
        assert soul.id is not None and soul.id != ""
        assert soul.role is not None and soul.role != ""
        assert soul.system_prompt is not None and soul.system_prompt != ""
