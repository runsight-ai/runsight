"""
Tests for RUN-201: Remove PlaceholderBlock from core engine.

Verifies that dynamic injection raises ValueError instead of falling back to
PlaceholderBlock, and that shared test infrastructure exists in conftest.py.
"""

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
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
# 1. Dynamic injection raises ValueError for unregistered step types
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
# 2. Test infrastructure exists in conftest.py
# ===========================================================================


class TestConfTestInfrastructure:
    """Verify that shared test infrastructure has been added to conftest.py."""

    def test_make_test_yaml_helper_exists(self):
        """conftest.py must export a make_test_yaml() helper function."""
        # Import from conftest (pytest makes it available as a module in tests/)
        try:
            from conftest import make_test_yaml
        except ImportError:
            pytest.fail("make_test_yaml must be defined in packages/core/tests/conftest.py")

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
