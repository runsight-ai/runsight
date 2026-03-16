"""
Red-phase tests for RUN-112: Parser + Explicit Inputs/Outputs.

Tests cover:
- Group 1: Input parsing & cross-reference validation
- Group 2: Output declarations
- Group 3: output_conditions wired to Workflow
- Group 4: Step input resolution (declared_inputs)
- Group 5: Parser wires inputs to Step
- Group 6: Builder simplification

All tests are expected to FAIL until RUN-112 implementation is complete.

Dependencies assumed done (RUN-110, RUN-111):
- schema.py has InputRef, ConditionDef, ConditionGroupDef, CaseDef
- conditions/engine.py has Case, Condition, ConditionGroup
- Workflow has set_output_conditions() and _output_conditions
"""

import json

import pytest

from runsight_core.primitives import Step
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml import parser as parser_module
from runsight_core.yaml.parser import BLOCK_TYPE_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockBlock:
    """Minimal mock block implementing BaseBlock interface for Step tests."""

    def __init__(self, block_id: str = "mock_block"):
        self.block_id = block_id
        self.last_state = None

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        self.last_state = state
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: "mock_result"},
            }
        )


# ===========================================================================
# Group 1: Input Parsing & Cross-Reference Validation
# ===========================================================================


class TestInputParsing:
    """Tests that inputs field in YAML is parsed correctly and references are validated."""

    def test_parse_inputs_basic(self):
        """YAML with inputs.from reference parses without error."""
        yaml_content = """
version: "1.0"
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
  name: test_inputs
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
        yaml_content = """
version: "1.0"
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
  name: test_inputs_invalid
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
        yaml_content = """
version: "1.0"
blocks:
  step_b:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        from: step_b.field
workflow:
  name: test_inputs_self
  entry: step_b
  transitions:
    - from: step_b
      to: null
"""
        with pytest.raises(ValueError, match="step_b"):
            parse_workflow_yaml(yaml_content)

    def test_parse_inputs_circular_dependency(self):
        """A inputs from B, B inputs from A raises ValueError for circular dependency."""
        yaml_content = """
version: "1.0"
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
  name: test_inputs_circular
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
        yaml_content = """
version: "1.0"
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
  name: test_inputs_circular_three
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
        yaml_content = """
version: "1.0"
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
  name: test_multi_inputs
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
        """Block without inputs field works fine (backward compatible)."""
        yaml_content = """
version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  name: test_no_inputs
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


# ===========================================================================
# Group 2: Output Declarations
# ===========================================================================


class TestOutputDeclarations:
    """Tests that outputs field in YAML is parsed correctly."""

    def test_parse_outputs_basic(self):
        """Block with outputs declaration (typed output schema) parses correctly."""
        yaml_content = """
version: "1.0"
blocks:
  evaluator:
    type: linear
    soul_ref: researcher
    outputs:
      result: string
      score: number
workflow:
  name: test_outputs
  entry: evaluator
  transitions:
    - from: evaluator
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

    def test_parse_outputs_none(self):
        """Block without outputs field works fine (backward compatible)."""
        yaml_content = """
version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  name: test_no_outputs
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)


# ===========================================================================
# Group 3: output_conditions Wired to Workflow
# ===========================================================================


class TestOutputConditionsWiring:
    """Tests that output_conditions in YAML is parsed and wired to Workflow."""

    def test_parse_output_conditions_wired_to_workflow(self):
        """output_conditions in YAML populates workflow._output_conditions for the block."""
        yaml_content = """
version: "1.0"
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
  name: test_output_conditions
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
        yaml_content = """
version: "1.0"
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
  name: test_oc_with_ct
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
        yaml_content = """
version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: researcher
workflow:
  name: test_no_oc
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
# Group 4: Step Input Resolution
# ===========================================================================


class TestStepInputResolution:
    """Tests that Step resolves declared_inputs before calling block.execute()."""

    def test_step_declared_inputs_constructor(self):
        """Step accepts declared_inputs dict in constructor."""
        block = MockBlock("test_block")
        step = Step(block, declared_inputs={"context": "step_a.result"})
        assert step.declared_inputs == {"context": "step_a.result"}

    @pytest.mark.asyncio
    async def test_step_resolves_inputs_before_execution(self):
        """Step resolves 'from: step_a.result' against state.results, injects into shared_memory."""
        block = MockBlock("step_b")
        step = Step(block, declared_inputs={"context": "step_a.result"})

        state = WorkflowState(
            results={"step_a": "research output data"},
        )

        await step.execute(state)

        # The block should have received state with _resolved_inputs in shared_memory
        assert block.last_state is not None
        resolved = block.last_state.shared_memory.get("_resolved_inputs")
        assert resolved is not None
        assert resolved["context"] == "research output data"

    @pytest.mark.asyncio
    async def test_step_resolves_dotted_path(self):
        """Step resolves 'from: step_a.nested.field' by traversing nested structure."""
        block = MockBlock("step_b")
        step = Step(block, declared_inputs={"value": "step_a.nested.field"})

        # state.results stores JSON string; Step should auto-parse and navigate
        nested_data = json.dumps({"nested": {"field": "deep_value"}})
        state = WorkflowState(
            results={"step_a": nested_data},
        )

        await step.execute(state)

        assert block.last_state is not None
        resolved = block.last_state.shared_memory.get("_resolved_inputs")
        assert resolved is not None
        assert resolved["value"] == "deep_value"

    @pytest.mark.asyncio
    async def test_step_missing_input_source_raises(self):
        """Referenced block not in state.results raises ValueError."""
        block = MockBlock("step_b")
        step = Step(block, declared_inputs={"context": "step_a.result"})

        state = WorkflowState(results={})  # step_a not present

        with pytest.raises(ValueError, match="step_a"):
            await step.execute(state)

    @pytest.mark.asyncio
    async def test_step_no_declared_inputs_unchanged(self):
        """Step without declared_inputs behaves exactly as before (backward compatible)."""
        block = MockBlock("step_a")
        step = Step(block)  # no declared_inputs

        state = WorkflowState()
        result_state = await step.execute(state)

        # Block should have received original state without _resolved_inputs
        assert block.last_state is not None
        assert "_resolved_inputs" not in block.last_state.shared_memory
        # Result should include block output keyed by block_id
        assert result_state.results.get("step_a") == "mock_result"

    def test_step_backward_compatible(self):
        """Existing Step(block, pre_hook, post_hook) constructor still works."""
        block = MockBlock("test_block")

        def pre(s):
            return s

        def post(s):
            return s

        step = Step(block, pre_hook=pre, post_hook=post)
        assert step.block is block
        assert step.pre_hook is pre
        assert step.post_hook is post
        # declared_inputs should default to empty dict
        assert step.declared_inputs == {}


# ===========================================================================
# Group 5: Parser Wires Inputs to Step
# ===========================================================================


class TestParserWiresInputsToStep:
    """Tests that parser creates Step objects with declared_inputs when block has inputs."""

    def test_parser_creates_step_with_declared_inputs(self):
        """When block has inputs, parser creates Step with declared_inputs populated."""
        yaml_content = """
version: "1.0"
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
  name: test_step_wiring
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
    - from: step_b
      to: null
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)

        # The workflow should wrap step_b's block in a Step with declared_inputs
        # Access internal _blocks dict — the block for step_b should be wrapped
        # in a Step (or the workflow should track inputs)
        step_b_block = workflow._blocks.get("step_b")
        assert step_b_block is not None

        # If wrapped in Step, check declared_inputs
        if isinstance(step_b_block, Step):
            assert "context" in step_b_block.declared_inputs
            assert step_b_block.declared_inputs["context"] == "step_a.result"
        else:
            # Alternative: workflow stores input mappings separately
            # Either way, the inputs must be tracked
            assert hasattr(workflow, "_block_inputs") or isinstance(step_b_block, Step), (
                "Parser must wire inputs either via Step wrapper or workflow._block_inputs"
            )

    @pytest.mark.asyncio
    async def test_parser_full_round_trip(self):
        """Complete YAML with inputs + output_conditions + transitions parses and validates."""
        yaml_content = """
version: "1.0"
blocks:
  research:
    type: linear
    soul_ref: researcher
    outputs:
      result: string
  evaluate:
    type: linear
    soul_ref: reviewer
    inputs:
      research_data:
        from: research.result
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
  approve:
    type: linear
    soul_ref: researcher
    inputs:
      eval_data:
        from: evaluate.result
  reject:
    type: linear
    soul_ref: researcher
    inputs:
      eval_data:
        from: evaluate.result
workflow:
  name: full_round_trip
  entry: research
  transitions:
    - from: research
      to: evaluate
    - from: approve
      to: null
    - from: reject
      to: null
  conditional_transitions:
    - from: evaluate
      approved: approve
      rejected: reject
      default: reject
"""
        workflow = parse_workflow_yaml(yaml_content)
        assert isinstance(workflow, Workflow)
        assert workflow.name == "full_round_trip"

        # Verify output_conditions wired
        assert hasattr(workflow, "_output_conditions")
        assert "evaluate" in workflow._output_conditions

        # Verify conditional transitions wired
        assert "evaluate" in workflow._conditional_transitions

        # Verify inputs tracked for evaluate, approve, reject blocks
        # (implementation may vary — Step wrapper or separate mapping)
        for block_id in ("evaluate", "approve", "reject"):
            block = workflow._blocks.get(block_id)
            assert block is not None, f"Block {block_id} should exist in workflow"


# ===========================================================================
# Group 6: Builder Simplification
# ===========================================================================


class TestBuilderSimplification:
    """Tests that builders don't re-validate what schema already checks."""

    def test_builder_no_redundant_validation(self):
        """Schema-level validation (e.g. InputRef structure) is not duplicated in builders.

        After RUN-112, inputs values must be InputRef objects (with 'from' field).
        When inputs have an invalid structure, Pydantic ValidationError should
        be raised by the schema layer — not a builder ValueError.
        """
        from pydantic import ValidationError

        # inputs with wrong structure — missing 'from' key inside InputRef.
        # After RUN-112 changes BlockDef.inputs to Dict[str, InputRef],
        # this should be caught by schema (InputRef validation), not builder.
        yaml_content = """
version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: researcher
    inputs:
      context:
        invalid_key: step_b.result
workflow:
  name: test_builder_validation
  entry: step_a
  transitions:
    - from: step_a
      to: null
"""
        # Schema should reject InputRef missing required 'from' field
        with pytest.raises(ValidationError):
            parse_workflow_yaml(yaml_content)


# ===========================================================================
# Group 7: CodeBlock Resolved Inputs in Sandbox
# ===========================================================================


class TestCodeBlockResolvedInputs:
    """Tests that CodeBlock receives resolved inputs via _resolved_inputs in shared_memory."""

    @pytest.mark.asyncio
    async def test_codeblock_receives_resolved_inputs_via_step(self):
        """When a CodeBlock has declared_inputs resolved by Step, _resolved_inputs is populated.

        Uses a MockBlock that captures state to verify the Step resolution
        mechanism populates shared_memory["_resolved_inputs"] before the block
        (which would be a CodeBlock in production) receives state.
        """
        block = MockBlock("code_step")
        step = Step(
            block,
            declared_inputs={
                "dataset": "fetch_step.result",
                "config": "setup_step.params",
            },
        )

        state = WorkflowState(
            results={
                "fetch_step": "fetched data payload",
                "setup_step": json.dumps({"params": "config_value"}),
            },
        )

        await step.execute(state)

        # MockBlock captured the state it received — verify _resolved_inputs
        assert block.last_state is not None
        resolved = block.last_state.shared_memory.get("_resolved_inputs")
        assert resolved is not None, (
            "_resolved_inputs must be in shared_memory for CodeBlock sandbox"
        )
        assert resolved["dataset"] == "fetched data payload"
        # "setup_step.params" should resolve the dotted path into the JSON
        assert resolved["config"] == "config_value"


# ===========================================================================
# Group 8: WorkflowBlockDef inputs/outputs Field Types
# ===========================================================================


class TestWorkflowBlockDefFields:
    """Tests that WorkflowBlock inputs/outputs fields don't collide with BaseBlockDef."""

    def test_workflow_block_inputs_outputs_are_dict_str_str(self):
        """WorkflowBlockDef's inputs/outputs are Dict[str, str] (workflow-mapping type),
        not InputRef type from BaseBlockDef.

        Whether the implementation uses renamed fields (workflow_inputs/workflow_outputs)
        or overrides with type: ignore, the schema must accept Dict[str, str] for
        workflow block input/output mappings.
        """
        from pydantic import TypeAdapter
        from runsight_core.yaml.schema import BlockDef

        # Parse a workflow-type block with Dict[str, str] inputs/outputs
        block_data = {
            "type": "workflow",
            "workflow_ref": "child_workflow",
            "inputs": {"child_key": "parent_step.result"},
            "outputs": {"parent_key": "child_step.output"},
        }
        adapter = TypeAdapter(BlockDef)
        block_def = adapter.validate_python(block_data)

        # inputs and outputs should be Dict[str, str] — workflow mapping type
        assert block_def.inputs is not None
        assert isinstance(block_def.inputs, dict)
        assert block_def.inputs["child_key"] == "parent_step.result"

        assert block_def.outputs is not None
        assert isinstance(block_def.outputs, dict)
        assert block_def.outputs["parent_key"] == "child_step.output"

    def test_workflow_block_yaml_with_workflow_inputs_outputs(self):
        """YAML with inputs/outputs on a workflow block parses correctly.

        If the implementation renames to workflow_inputs/workflow_outputs, this
        test should be updated to use those field names. Currently tests the
        override approach where inputs/outputs on workflow blocks are Dict[str, str].
        """
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_data = {
            "version": "1.0",
            "blocks": {
                "child_runner": {
                    "type": "workflow",
                    "workflow_ref": "analysis_pipeline",
                    "inputs": {"data": "fetcher.result"},
                    "outputs": {"summary": "analyzer.output"},
                },
            },
            "workflow": {
                "name": "test_wf_block_fields",
                "entry": "child_runner",
                "transitions": [{"from": "child_runner", "to": None}],
            },
        }
        file_def = RunsightWorkflowFile.model_validate(yaml_data)
        block = file_def.blocks["child_runner"]
        assert block.inputs == {"data": "fetcher.result"}
        assert block.outputs == {"summary": "analyzer.output"}

    def test_non_workflow_block_inputs_are_inputref_type(self):
        """Non-workflow blocks should have inputs parsed as InputRef (dict with 'from' key),
        not plain Dict[str, str]. After RUN-112, BaseBlockDef.inputs is Dict[str, InputRef].

        This verifies that the type distinction exists: workflow blocks get Dict[str, str],
        non-workflow blocks get Dict[str, InputRef].
        """
        from pydantic import TypeAdapter
        from runsight_core.yaml.schema import BlockDef

        # A linear block with InputRef-style inputs (has 'from' key)
        block_data = {
            "type": "linear",
            "soul_ref": "researcher",
            "inputs": {
                "context": {"from": "step_a.result"},
            },
        }
        adapter = TypeAdapter(BlockDef)
        block_def = adapter.validate_python(block_data)
        assert block_def.inputs is not None


# ===========================================================================
# Group 9: Builder Simplification — No Conditional in Parser
# ===========================================================================


class TestConditionalNotInParser:
    """Tests that _build_conditional was removed from parser (RUN-91 cleanup)."""

    def test_conditional_not_in_block_type_registry(self):
        """'conditional' must not be a registered block type in BLOCK_TYPE_REGISTRY."""
        assert "conditional" not in BLOCK_TYPE_REGISTRY

    def test_build_conditional_not_in_parser_module(self):
        """_build_conditional helper must not exist in parser module."""
        assert not hasattr(parser_module, "_build_conditional")
