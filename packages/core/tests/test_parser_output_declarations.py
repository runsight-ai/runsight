"""Parser input, output, condition, and Step wiring behavior."""

from parser_yaml_helpers import researcher_reviewer_souls_yaml
from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.blocks.base import BaseBlock
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


class TestOutputDeclarations:
    """Tests that outputs field in YAML is parsed correctly."""

    def test_parse_outputs_basic(self):
        """Block with outputs declaration (typed output schema) parses correctly."""
        yaml_content = f"""
version: "1.0"
id: typed_outputs_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  evaluator:
    type: linear
    soul_ref: researcher
    outputs:
      result: string
      score: number
workflow:
  id: typed_outputs_workflow
  kind: workflow
  name: typed_outputs_workflow
  entry: evaluator
  transitions:
    - from: evaluator
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

    def test_parse_outputs_none(self):
        """Block without outputs field uses the legacy default path."""
        yaml_content = f"""
version: "1.0"
id: no_outputs_workflow
kind: workflow
{researcher_reviewer_souls_yaml()}
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  id: no_outputs_workflow
  kind: workflow
  name: no_outputs_workflow
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


# ===========================================================================
# output_conditions wiring to Workflow
# ===========================================================================
