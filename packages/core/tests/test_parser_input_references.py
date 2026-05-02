"""Parser input, output, condition, and Step wiring behavior."""

import pytest
from parser_yaml_helpers import researcher_reviewer_souls_yaml
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Step
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockBlock:
    """Minimal mock block implementing BaseBlock interface for Step tests."""

    def __init__(self, block_id: str = "mock_block"):
        self.block_id = block_id
        self.last_state = None

    async def execute(self, ctx):
        from runsight_core.block_io import BlockOutput

        self.last_state = ctx.state_snapshot
        return BlockOutput(output="mock_result")


class CapturingBlock(BaseBlock):
    """New-style block that captures the BlockContext it receives."""

    def __init__(self, block_id: str = "capturing_block"):
        super().__init__(block_id=block_id)
        self.received_ctx: BlockContext | None = None

    async def execute(self, ctx: BlockContext) -> BlockOutput:
        self.received_ctx = ctx
        return BlockOutput(output="captured")


# ===========================================================================
# Input parsing and cross-reference validation
# ===========================================================================


class TestInputParsing:
    """Tests that inputs field in YAML is parsed correctly and references are validated."""

    def test_parse_inputs_basic(self):
        """YAML with inputs.from reference parses without error."""
        yaml_content = f"""
version: "1.0"
id: inputs_cross_reference_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: step_a.result
workflow:
  id: inputs_cross_reference_workflow
  kind: workflow
  name: inputs_cross_reference_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

        # Verify the parsed workflow retained the input information on step_b
        step_b_block = workflow._blocks.get("step_b")
        assert step_b_block is not None, "step_b must exist in workflow._blocks"
        # If wrapped in Step, declared_inputs should contain the input reference
        if isinstance(step_b_block, Step):
            assert "context" in step_b_block.declared_inputs
            assert step_b_block.declared_inputs["context"] == "step_a.result"
        else:
            # Alternative: workflow tracks input mappings separately
            assert hasattr(workflow, "_block_inputs"), (
                "Parser must track inputs via Step wrapper or workflow._block_inputs"
            )

    def test_parse_inputs_invalid_block_ref(self):
        """inputs.from referencing nonexistent block raises ValueError with clear message."""
        yaml_content = f"""
version: "1.0"
id: invalid_input_reference_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: nonexistent_block.field
workflow:
  id: invalid_input_reference_workflow
  kind: workflow
  name: invalid_input_reference_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null
"""
        with pytest.raises(ValueError, match="nonexistent_block"):
            parse_workflow_yaml(yaml_content)

    def test_parse_inputs_self_reference(self):
        """inputs.from referencing self (same block) raises ValueError for circular dependency."""
        yaml_content = f"""
version: "1.0"
id: self_reference_input_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: step_b.field
workflow:
  id: self_reference_input_workflow
  kind: workflow
  name: self_reference_input_workflow
  entry: step_b
  transitions:
    - from: step_b
      to: null
"""
        with pytest.raises(ValueError, match="step_b"):
            parse_workflow_yaml(yaml_content)

    def test_parse_inputs_circular_dependency(self):
        """A inputs from B, B inputs from A raises ValueError for circular dependency."""
        yaml_content = f"""
version: "1.0"
id: two_node_input_cycle_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
    inputs:
      data:
        from: step_b.result
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: step_a.result
workflow:
  id: two_node_input_cycle_workflow
  kind: workflow
  name: two_node_input_cycle_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null
"""
        with pytest.raises(ValueError, match="circular|cycle"):
            parse_workflow_yaml(yaml_content)

    def test_parse_inputs_circular_dependency_three_nodes(self):
        """A->B->C->A circular input dependency chain raises ValueError."""
        yaml_content = f"""
version: "1.0"
id: three_node_input_cycle_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
    inputs:
      data:
        from: step_c.result
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: step_a.result
  step_c:
    type: linear
    soul_ref: researcher
    inputs:
      feedback:
        from: step_b.result
workflow:
  id: three_node_input_cycle_workflow
  kind: workflow
  name: three_node_input_cycle_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: step_c
    - from: step_c
      to: null
"""
        with pytest.raises(ValueError, match="circular|cycle"):
            parse_workflow_yaml(yaml_content)

    def test_parse_inputs_multiple_inputs(self):
        """Block with multiple input references parses all correctly."""
        yaml_content = f"""
version: "1.0"
id: multiple_declared_inputs_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
  step_b:
    type: linear
    soul_ref: reviewer
  step_c:
    type: linear
    soul_ref: researcher
    inputs:
      research_context:
        from: step_a.result
      review_feedback:
        from: step_b.summary
      review_score:
        from: step_b.score
workflow:
  id: multiple_declared_inputs_workflow
  kind: workflow
  name: multiple_declared_inputs_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: step_c
    - from: step_c
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

    def test_parse_inputs_no_inputs(self):
        """Block without inputs field uses the legacy default path."""
        yaml_content = f"""
version: "1.0"
id: no_declared_inputs_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  id: no_declared_inputs_workflow
  kind: workflow
  name: no_declared_inputs_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


# ===========================================================================
# Output declarations
# ===========================================================================
