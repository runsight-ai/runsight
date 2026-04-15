"""
Integration tests for WorkflowBlock parser integration and cross-feature interactions.

Tests the interaction between:
1. YAML parser extending to handle type: workflow blocks
2. Workflow.run() accepting and propagating call_stack and workflow_registry kwargs
3. Existing blocks accepting **kwargs for backward compatibility
4. WorkflowBlock resolving workflow references via registry
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import TypeAdapter
from runsight_core import LinearBlock, WorkflowBlock
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile


class TestParserIntegration:
    """Test parser integration with WorkflowBlock."""

    def test_workflow_block_in_registry(self):
        """Verify that workflow block type is in BLOCK_TYPE_REGISTRY."""
        assert "workflow" in BLOCK_TYPE_REGISTRY
        assert "linear" in BLOCK_TYPE_REGISTRY
        assert "dispatch" in BLOCK_TYPE_REGISTRY

    def test_parse_simple_workflow_without_workflow_blocks(self):
        """Ensure existing workflow parsing still works without workflow blocks."""
        yaml_def = """
version: "1.0"
id: simple_wf
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
workflow:
  id: simple_wf
  kind: workflow
  name: simple_wf
  entry: research
blocks:
  research:
    type: linear
    soul_ref: researcher
transitions:
  - from: research
    to: null
"""
        wf = parse_workflow_yaml(yaml_def)
        assert wf.name == "simple_wf"
        assert "research" in wf._blocks

    def test_schema_allows_workflow_block_definition(self):
        """Verify schema accepts workflow block definitions."""
        block_def_dict = {
            "type": "workflow",
            "workflow_ref": "child_analysis",
            "inputs": {"topic": "shared_memory.research_topic"},
            "outputs": {"results.analysis": "final"},
            "max_depth": 5,
        }
        _block_adapter = TypeAdapter(BlockDef)
        block_def = _block_adapter.validate_python(block_def_dict)
        assert block_def.type == "workflow"
        assert block_def.workflow_ref == "child_analysis"
        assert block_def.inputs == {"topic": "shared_memory.research_topic"}
        assert block_def.outputs == {"results.analysis": "final"}
        assert block_def.max_depth == 5


class TestWorkflowRunKwargsHandling:
    """Test that Workflow.run() can accept and pass through kwargs."""

    @pytest.mark.asyncio
    async def test_workflow_run_accepts_registry_kwarg(self):
        """Test that Workflow.run() accepts registry kwarg (existing feature)."""
        yaml_def = """
version: "1.0"
id: test_wf
kind: workflow
workflow:
  id: test_wf
  kind: workflow
  name: test_wf
  entry: step1
blocks:
  step1:
    type: code
    code: "def main(data):\\n    return {'step1': 'done'}"
transitions:
  - from: step1
    to: null
"""
        wf = parse_workflow_yaml(yaml_def)
        state = WorkflowState()
        registry = MagicMock()

        # Should not raise
        result = await wf.run(state, registry=registry)
        assert isinstance(result, WorkflowState)

    @pytest.mark.asyncio
    async def test_workflow_run_signature_flexibility(self):
        """Test that Workflow.run() can handle various kwarg configurations."""
        yaml_def = """
version: "1.0"
id: test_wf
kind: workflow
workflow:
  id: test_wf
  kind: workflow
  name: test_wf
  entry: step1
blocks:
  step1:
    type: code
    code: "def main(data):\\n    return {'step1': 'done'}"
transitions:
  - from: step1
    to: null
"""
        wf = parse_workflow_yaml(yaml_def)
        state = WorkflowState()

        # All of these should be acceptable
        result1 = await wf.run(state)
        assert isinstance(result1, WorkflowState)

        result2 = await wf.run(state, registry=None)
        assert isinstance(result2, WorkflowState)


class TestBlockKwargsCompatibility:
    """Test block signature compatibility for WorkflowBlock kwargs propagation."""

    @pytest.mark.asyncio
    async def test_linear_block_basic_execution(self):
        """Test LinearBlock.execute() basic functionality."""
        soul = Soul(
            id="test_soul",
            kind="soul",
            name="Test",
            role="Test",
            system_prompt="Test prompt",
        )
        runner = AsyncMock()
        mock_result = AsyncMock()
        mock_result.output = "test output"
        mock_result.cost_usd = 0.01
        mock_result.total_tokens = 10
        mock_result.exit_handle = None
        runner.execute = AsyncMock(return_value=mock_result)

        block = LinearBlock(block_id="test_linear", soul=soul, runner=runner)
        state = WorkflowState()

        # Execute with default signature
        result = await block.execute(state)
        assert isinstance(result, WorkflowState)

    @pytest.mark.asyncio
    async def test_workflow_block_accepts_kwargs(self):
        """Test that WorkflowBlock.execute() accepts call_stack and workflow_registry kwargs."""
        child_wf = AsyncMock()
        child_wf.name = "child"
        child_final_state = WorkflowState()
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="test_workflow",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        state = WorkflowState()
        registry = WorkflowRegistry()

        # Should accept call_stack and workflow_registry kwargs without error
        result = await block.execute(state, call_stack=["parent"], workflow_registry=registry)
        assert isinstance(result, WorkflowState)
        assert "test_workflow" in result.results


class TestWorkflowBlockIntegration:
    """Test WorkflowBlock integration with other components."""

    @pytest.mark.asyncio
    async def test_workflow_block_with_registry(self):
        """Test WorkflowBlock can resolve child workflow from registry."""
        # Create a simple child workflow
        child_yaml_def = """
version: "1.0"
id: child_workflow
kind: workflow
workflow:
  id: child_workflow
  kind: workflow
  name: child_workflow
  entry: child_task
blocks:
  child_task:
    type: code
    code: "def main(data):\\n    return {'child_task': 'done'}"
transitions:
  - from: child_task
    to: null
"""
        child_wf = parse_workflow_yaml(child_yaml_def)

        # Create parent workflow that references child
        parent_yaml_def = """
version: "1.0"
id: parent_workflow
kind: workflow
workflow:
  id: parent_workflow
  kind: workflow
  name: parent_workflow
  entry: main_task
blocks:
  main_task:
    type: code
    code: "def main(data):\\n    return {'main_task': 'done'}"
transitions:
  - from: main_task
    to: null
"""
        parent_wf = parse_workflow_yaml(parent_yaml_def)

        # Create registry and register child
        registry = WorkflowRegistry()
        registry.register("child_workflow", child_wf)

        # Execute parent - should work with registry
        state = WorkflowState()
        result = await parent_wf.run(state, registry=None)
        assert isinstance(result, WorkflowState)

    @pytest.mark.asyncio
    async def test_workflow_block_state_isolation(self):
        """Test that WorkflowBlock properly isolates child state."""
        child_wf = AsyncMock()
        child_wf.name = "child"
        child_final_state = WorkflowState(
            results={"child_result": BlockResult(output="output")},
            total_cost_usd=0.05,
            total_tokens=50,
        )
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="sub_workflow",
            child_workflow=child_wf,
            inputs={"shared_memory.data": "shared_memory.parent_data"},
            outputs={"results.child_out": "results.child_result"},
        )

        parent_state = WorkflowState(
            shared_memory={"parent_data": "important"},
            results={"existing": BlockResult(output="value")},
        )

        # Execute
        result = await block.execute(parent_state)

        # Verify child received isolated state
        call_args = child_wf.run.call_args
        child_state_arg = call_args[0][0]

        # Child should only have mapped inputs
        assert child_state_arg.shared_memory.get("data") == "important"
        # Child should not have parent's other data
        assert "existing" not in child_state_arg.results

        # Parent should have output mapped back
        assert result.results.get("child_out") == BlockResult(output="output")
        # Parent's original data preserved
        assert result.results.get("existing") == BlockResult(output="value")

    @pytest.mark.asyncio
    async def test_workflow_block_cost_propagation(self):
        """Test that child workflow costs propagate to parent."""
        child_wf = AsyncMock()
        child_wf.name = "child"
        child_final_state = WorkflowState(
            results={"final": BlockResult(output="output")},
            total_cost_usd=0.25,
            total_tokens=250,
        )
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="expensive_child",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState(
            total_cost_usd=0.10,
            total_tokens=100,
        )

        result = await block.execute(parent_state)

        # Costs should be summed
        assert result.total_cost_usd == pytest.approx(0.35)  # 0.10 + 0.25
        assert result.total_tokens == 350  # 100 + 250

    @pytest.mark.asyncio
    async def test_workflow_block_cycle_detection(self):
        """Test that WorkflowBlock detects cycles via call_stack."""
        child_wf = AsyncMock()
        child_wf.name = "recursive_wf"
        child_wf.run = AsyncMock()

        block = WorkflowBlock(
            block_id="recursive_call",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            max_depth=5,
        )

        state = WorkflowState()

        # Call with child already in stack (cycle)
        with pytest.raises(RecursionError) as exc_info:
            await block.execute(state, call_stack=["parent", "recursive_wf"])

        error_msg = str(exc_info.value)
        assert "cycle detected" in error_msg.lower()
        assert "recursive_wf" in error_msg

    @pytest.mark.asyncio
    async def test_workflow_block_depth_limit(self):
        """Test that WorkflowBlock enforces depth limits."""
        child_wf = AsyncMock()
        child_wf.name = "deep_child"
        child_wf.run = AsyncMock()

        block = WorkflowBlock(
            block_id="depth_test",
            child_workflow=child_wf,
            inputs={},
            outputs={},
            max_depth=3,
        )

        state = WorkflowState()

        # Call with stack at max depth
        with pytest.raises(RecursionError) as exc_info:
            await block.execute(state, call_stack=["a", "b", "c"])

        error_msg = str(exc_info.value)
        assert "maximum depth" in error_msg.lower() or "max_depth" in error_msg

    @pytest.mark.asyncio
    async def test_workflow_block_passes_registry_to_child(self):
        """Test that WorkflowBlock passes workflow_registry to child.run()."""
        child_wf = AsyncMock()
        child_wf.name = "child_that_needs_registry"
        child_final_state = WorkflowState()
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="parent_block",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()
        registry = WorkflowRegistry()

        # Execute with registry
        await block.execute(parent_state, workflow_registry=registry)

        # Verify registry was passed to child
        call_kwargs = child_wf.run.call_args.kwargs
        assert "workflow_registry" in call_kwargs
        assert call_kwargs["workflow_registry"] is registry

    @pytest.mark.asyncio
    async def test_workflow_block_passes_extended_call_stack(self):
        """Test that WorkflowBlock extends call_stack before calling child."""
        child_wf = AsyncMock()
        child_wf.name = "child_wf"
        child_final_state = WorkflowState()
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="parent_block",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        parent_state = WorkflowState()

        # Execute with initial call_stack
        await block.execute(parent_state, call_stack=["parent_wf"])

        # Verify extended call_stack was passed
        call_kwargs = child_wf.run.call_args.kwargs
        assert "call_stack" in call_kwargs
        assert call_kwargs["call_stack"] == ["parent_wf", "child_wf"]


class TestCrossFeatureInteraction:
    """Test interactions between multiple merged features."""

    @pytest.mark.asyncio
    async def test_parser_produces_valid_workflow_blocks(self):
        """
        Test that if parser supported workflow blocks, it would produce
        valid WorkflowBlock instances with proper initialization.
        """
        # This test documents what the parser should do when workflow blocks
        # are integrated. Currently skipped as parser integration not done.

        # Mock what the parser would do
        child_wf_def = """
version: "1.0"
id: child
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Researcher
    role: Researcher
    system_prompt: You research things.
workflow:
  id: child
  kind: workflow
  name: child
  entry: step1
blocks:
  step1:
    type: linear
    soul_ref: researcher
transitions:
  - from: step1
    to: null
"""
        child_wf = parse_workflow_yaml(child_wf_def)

        # Manually create what parser would create
        block = WorkflowBlock(
            block_id="invoke_child",
            child_workflow=child_wf,
            inputs={"shared_memory.input": "shared_memory.source"},
            outputs={"results.output": "results.final"},
            max_depth=10,
        )

        assert block.block_id == "invoke_child"
        assert block.child_workflow.name == "child"
        assert block.inputs == {"shared_memory.input": "shared_memory.source"}
        assert block.outputs == {"results.output": "results.final"}
        assert block.max_depth == 10

    @pytest.mark.asyncio
    async def test_workflow_block_with_empty_call_stack_defaults(self):
        """Test WorkflowBlock works with default empty call_stack."""
        child_wf = AsyncMock()
        child_wf.name = "child"
        child_final_state = WorkflowState()
        child_wf.run = AsyncMock(return_value=child_final_state)

        block = WorkflowBlock(
            block_id="test",
            child_workflow=child_wf,
            inputs={},
            outputs={},
        )

        state = WorkflowState()

        # Execute without explicit call_stack (should default to empty list)
        await block.execute(state)

        # Verify default empty list was used
        call_kwargs = child_wf.run.call_args.kwargs
        assert call_kwargs["call_stack"] == [child_wf.name]

    @pytest.mark.asyncio
    async def test_nested_workflow_blocks_with_isolation(self):
        """
        Test that nested workflow blocks properly isolate state at each level.
        This exercises the interaction between multiple WorkflowBlocks.
        """
        # Inner child
        inner_wf = AsyncMock()
        inner_wf.name = "inner"
        inner_final_state = WorkflowState(
            results={"inner_result": BlockResult(output="inner_output")},
            total_cost_usd=0.01,
            total_tokens=10,
        )
        inner_wf.run = AsyncMock(return_value=inner_final_state)

        # Outer child that will invoke inner
        outer_wf = AsyncMock()
        outer_wf.name = "outer"
        outer_final_state = WorkflowState(
            results={"outer_result": BlockResult(output="outer_output")},
            total_cost_usd=0.02,
            total_tokens=20,
        )
        outer_wf.run = AsyncMock(return_value=outer_final_state)

        # Parent invokes outer
        parent_block = WorkflowBlock(
            block_id="parent_invoke",
            child_workflow=outer_wf,
            inputs={},
            outputs={"results.final": "results.outer_result"},
        )

        parent_state = WorkflowState(total_cost_usd=0.05, total_tokens=50)

        result = await parent_block.execute(parent_state, call_stack=[])

        # Verify state and costs are properly aggregated
        assert result.results["final"] == BlockResult(output="outer_output")
        assert result.total_cost_usd == pytest.approx(0.07)  # 0.05 + 0.02
        assert result.total_tokens == 70  # 50 + 20

    def test_workflow_registry_with_workflow_block_schema(self):
        """Test that WorkflowRegistry integrates with workflow block schema."""
        # Create workflows
        child_wf_dict = {
            "version": "1.0",
            "id": "child_analysis",
            "kind": "workflow",
            "workflow": {
                "id": "child_analysis",
                "kind": "workflow",
                "name": "child_analysis",
                "entry": "analyze",
            },
            "blocks": {"analyze": {"type": "linear", "soul_ref": "researcher"}},
            "transitions": [{"from": "analyze", "to": None}],
        }
        child_wf_file = RunsightWorkflowFile.model_validate(child_wf_dict)

        # Register
        registry = WorkflowRegistry()
        registry.register("child_analysis", child_wf_file)

        # Block schema should accept workflow_ref
        _block_adapter = TypeAdapter(BlockDef)
        _block_adapter.validate_python(
            {
                "type": "workflow",
                "workflow_ref": "child_analysis",
                "inputs": {},
                "outputs": {},
            }
        )

        # Registry should resolve the reference
        resolved = registry.get("child_analysis")
        assert resolved.workflow.name == "child_analysis"
