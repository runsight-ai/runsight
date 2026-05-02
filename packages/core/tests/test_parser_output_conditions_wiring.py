"""Parser input, output, condition, and Step wiring behavior."""

from parser_yaml_helpers import researcher_reviewer_souls_yaml
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.blocks.base import BaseBlock
from runsight_core.workflow import Workflow
from runsight_core.yaml import parser as parser_module
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


class TestOutputConditionsWiring:
    """Tests that output_conditions in YAML is parsed and wired to Workflow."""

    def test_parse_output_conditions_wired_to_workflow(self):
        """output_conditions in YAML populates workflow._output_conditions for the block."""
        yaml_content = f"""
version: "1.0"
id: output_conditions_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  evaluator:
    type: linear
    soul_ref: researcher
    output_conditions:
      - case_id: approved
        condition_group:
          combinator: and
          conditions:
            - eval_key: status
              operator: equals
              value: approved
      - case_id: rejected
        default: true
workflow:
  id: output_conditions_workflow
  kind: workflow
  name: output_conditions_workflow
  entry: evaluator
  transitions:
    - from: evaluator
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        # output_conditions should be wired to the workflow object
        assert hasattr(workflow, "_output_conditions")
        assert "evaluator" in workflow._output_conditions

    def test_parse_output_conditions_with_conditional_transition(self):
        """output_conditions on block + conditional_transition from that block both work together."""
        yaml_content = f"""
version: "1.0"
id: output_conditions_conditional_transition_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  evaluator:
    type: linear
    soul_ref: researcher
    output_conditions:
      - case_id: approved
        condition_group:
          combinator: and
          conditions:
            - eval_key: status
              operator: equals
              value: approved
      - case_id: rejected
        default: true
  approve_step:
    type: linear
    soul_ref: researcher
  reject_step:
    type: linear
    soul_ref: researcher
workflow:
  id: output_conditions_conditional_transition_workflow
  kind: workflow
  name: output_conditions_conditional_transition_workflow
  entry: evaluator
  conditional_transitions:
    - from: evaluator
      approved: approve_step
      rejected: reject_step
      default: reject_step
  transitions:
    - from: approve_step
      to: null
    - from: reject_step
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        # Both output_conditions and conditional_transitions should be present
        assert "evaluator" in workflow._output_conditions
        assert "evaluator" in workflow._conditional_transitions

    def test_parse_output_conditions_empty(self):
        """Block without output_conditions has no entry in workflow._output_conditions."""
        yaml_content = f"""
version: "1.0"
id: no_output_conditions_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  id: no_output_conditions_workflow
  kind: workflow
  name: no_output_conditions_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert hasattr(workflow, "_output_conditions")
        assert "step_a" not in workflow._output_conditions


# ===========================================================================
# Step input resolution
# ===========================================================================


class TestConditionalNotInParser:
    """_build_conditional remains outside parser module ownership."""

    def test_conditional_not_in_block_type_registry(self):
        """'conditional' must not be a registered block type in BLOCK_TYPE_REGISTRY."""
        assert "conditional" not in BLOCK_TYPE_REGISTRY

    def test_build_conditional_not_in_parser_module(self):
        """_build_conditional helper must not exist in parser module."""
        assert not hasattr(parser_module, "_build_conditional")
