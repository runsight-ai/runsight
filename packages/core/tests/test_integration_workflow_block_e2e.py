"""
End-to-end integration tests for WorkflowBlock feature.

Tests cross-feature interactions across schema, registry, parser, and execution:
- Schema validation at parse time
- Parser handling of workflow blocks with registry
- WorkflowBlock execution with state isolation and mapping
- Multi-level nested workflow execution
- Error handling across boundary layers
"""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import TypeAdapter
from runsight_core import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import BlockDef, RunsightWorkflowFile

_RESEARCHER_SOUL = {
    "researcher": {
        "id": "researcher",
        "kind": "soul",
        "name": "Researcher",
        "role": "Senior Researcher",
        "system_prompt": "You research topics.",
    }
}

# Minimal interface required by _validate_workflow_block_contract for any child workflow
_EMPTY_INTERFACE = {"inputs": [], "outputs": []}


class TestSchemaParsingIntegration:
    """Test schema validation at the boundary with parser."""

    def test_schema_enforces_workflow_ref_requirement(self):
        """
        Schema validator should require workflow_ref when type='workflow'.
        This is the first gate in the integration pipeline.
        """
        from pydantic import ValidationError

        _block_adapter = TypeAdapter(BlockDef)

        # Missing workflow_ref should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            _block_adapter.validate_python(
                {
                    "type": "workflow",
                    # workflow_ref missing - should fail
                }
            )

        error_str = str(exc_info.value).lower()
        assert "workflow_ref" in error_str

    def test_schema_allows_workflow_with_complete_fields(self):
        """Schema should accept all workflow block fields."""
        _block_adapter = TypeAdapter(BlockDef)
        block_def = _block_adapter.validate_python(
            {
                "type": "workflow",
                "workflow_ref": "child_pipeline",
                "inputs": {"task": "task.id"},
                "outputs": {"results.out": "summary"},
                "max_depth": 8,
            }
        )

        assert block_def.type == "workflow"
        assert block_def.workflow_ref == "child_pipeline"
        assert block_def.inputs == {"task": "task.id"}
        assert block_def.outputs == {"results.out": "summary"}
        assert block_def.max_depth == 8

    def test_schema_allows_workflow_with_minimal_fields(self):
        """Schema should allow minimal workflow block (just type and workflow_ref)."""
        _block_adapter = TypeAdapter(BlockDef)
        block_def = _block_adapter.validate_python(
            {
                "type": "workflow",
                "workflow_ref": "simple_child",
            }
        )

        assert block_def.type == "workflow"
        assert block_def.workflow_ref == "simple_child"
        assert block_def.inputs is None
        assert block_def.outputs is None
        assert block_def.max_depth is None


class TestParserRegistryIntegration:
    """Test parser interaction with WorkflowRegistry."""

    def test_parser_requires_registry_for_workflow_blocks(self):
        """
        Parser should raise clear error when workflow block present but no registry.
        This tests the parser's check at line 354-359.
        """
        yaml_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "child_ref": {
                    "type": "workflow",
                    "workflow_ref": "missing_child",
                }
            },
            "workflow": {
                "name": "parent",
                "entry": "child_ref",
                "transitions": [{"from": "child_ref", "to": None}],
            },
        }

        with pytest.raises(ValueError) as exc_info:
            parse_workflow_yaml(yaml_dict)  # No registry

        error_str = str(exc_info.value).lower()
        assert "registry" in error_str or "workflowregistry" in error_str

    def test_parser_resolves_workflow_from_registry(self):
        """
        Parser should resolve workflow_ref from registry and create WorkflowBlock.
        This tests lines 362-386 of parser.
        """
        # Create child workflow (interface required by _validate_workflow_block_contract)
        child_dict = {
            "version": "1.0",
            "id": "analysis-child",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"step1": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "analysis_child",
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        # Register child
        registry = WorkflowRegistry()
        registry.register("analysis_child", child_file)

        # Parse parent with workflow block
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke_analysis": {
                    "type": "workflow",
                    "workflow_ref": "analysis_child",
                }
            },
            "workflow": {
                "name": "main_workflow",
                "entry": "invoke_analysis",
                "transitions": [{"from": "invoke_analysis", "to": None}],
            },
        }

        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        # Verify WorkflowBlock was created
        assert isinstance(parent_wf, Workflow)
        assert "invoke_analysis" in parent_wf._blocks
        block = parent_wf._blocks["invoke_analysis"]
        assert isinstance(block, WorkflowBlock)
        assert block.child_workflow.name == "analysis_child"


class TestParserMaxDepthResolution:
    """Test parser's max_depth resolution logic (lines 367-372)."""

    def test_block_level_max_depth_overrides_global(self):
        """Block-level max_depth should override global config."""
        child_dict = {
            "version": "1.0",
            "id": "child-c",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"s": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {"name": "c", "entry": "s", "transitions": [{"from": "s", "to": None}]},
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "config": {"max_workflow_depth": 12},
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "c",
                    "max_depth": 5,  # Explicit override
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        block = wf._blocks["invoke"]
        assert block.max_depth == 5  # Block-level wins

    def test_global_config_used_when_no_block_level(self):
        """Global config should be used when block has no max_depth."""
        child_dict = {
            "version": "1.0",
            "id": "child-c",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"s": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {"name": "c", "entry": "s", "transitions": [{"from": "s", "to": None}]},
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "config": {"max_workflow_depth": 7},
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "c",
                    # No max_depth at block level
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        block = wf._blocks["invoke"]
        assert block.max_depth == 7

    def test_default_max_depth_used_when_neither_set(self):
        """Default 10 should be used when neither block nor config set."""
        child_dict = {
            "version": "1.0",
            "id": "child-c",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"s": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {"name": "c", "entry": "s", "transitions": [{"from": "s", "to": None}]},
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "c",
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        block = wf._blocks["invoke"]
        assert block.max_depth == 10


class TestParserNestedWorkflowRecursion:
    """Test parser's recursive parsing of nested workflows (line 365)."""

    def test_parser_recursively_parses_nested_workflow_blocks(self):
        """
        Parser should recursively parse child workflows that contain their own workflow blocks.
        This tests the parse_workflow_yaml(..., workflow_registry=workflow_registry) call.
        """
        # Grandchild (deepest level) — interface required at every level
        grandchild_dict = {
            "version": "1.0",
            "id": "grandchild",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"step": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "grandchild",
                "entry": "step",
                "transitions": [{"from": "step", "to": None}],
            },
        }
        grandchild_file = RunsightWorkflowFile.model_validate(grandchild_dict)

        # Child contains workflow block pointing to grandchild
        child_dict = {
            "version": "1.0",
            "id": "child",
            "kind": "workflow",
            "interface": _EMPTY_INTERFACE,
            "blocks": {
                "invoke_grandchild": {
                    "type": "workflow",
                    "workflow_ref": "grandchild",
                }
            },
            "workflow": {
                "name": "child",
                "entry": "invoke_grandchild",
                "transitions": [{"from": "invoke_grandchild", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        # Setup registry with both
        registry = WorkflowRegistry()
        registry.register("grandchild", grandchild_file)
        registry.register("child", child_file)

        # Parent invokes child
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child",
                }
            },
            "workflow": {
                "name": "parent",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        # Parse parent - should recursively handle nested workflow blocks
        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        # Verify structure
        assert parent_wf.name == "parent"
        parent_block = parent_wf._blocks["invoke_child"]
        assert isinstance(parent_block, WorkflowBlock)
        assert parent_block.child_workflow.name == "child"

        # Verify child was recursively parsed with workflow block
        child_block = parent_block.child_workflow._blocks["invoke_grandchild"]
        assert isinstance(child_block, WorkflowBlock)
        assert child_block.child_workflow.name == "grandchild"


@pytest.mark.asyncio
class TestWorkflowBlockExecutionIntegration:
    """Test WorkflowBlock execution at integration boundaries.

    NOTE: Full end-to-end execution of WorkflowBlocks requires Workflow.run()
    to accept call_stack and workflow_registry kwargs, which is not yet implemented.
    This is documented as an integration gap that requires updating Workflow.run()
    signature to accept **kwargs.
    """

    async def test_workflow_block_parses_in_workflow_graph(self):
        """
        WorkflowBlock should be created as a block in workflow graph by parser.
        This tests the parsing layer - execution requires Workflow.run() enhancement.
        """
        # Create child workflow (interface required by _validate_workflow_block_contract)
        child_dict = {
            "version": "1.0",
            "id": "research-child",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": _EMPTY_INTERFACE,
            "blocks": {"research": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "research_child",
                "entry": "research",
                "transitions": [{"from": "research", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("research_child", child_file)

        # Create parent with workflow block
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "setup": {"type": "linear", "soul_ref": "researcher"},
                "invoke_analysis": {
                    "type": "workflow",
                    "workflow_ref": "research_child",
                },
                "finalize": {"type": "linear", "soul_ref": "researcher"},
            },
            "workflow": {
                "name": "main",
                "entry": "setup",
                "transitions": [
                    {"from": "setup", "to": "invoke_analysis"},
                    {"from": "invoke_analysis", "to": "finalize"},
                    {"from": "finalize", "to": None},
                ],
            },
        }

        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        # Verify parser created the workflow block correctly
        assert "invoke_analysis" in parent_wf._blocks
        workflow_block = parent_wf._blocks["invoke_analysis"]
        assert isinstance(workflow_block, WorkflowBlock)
        assert workflow_block.child_workflow.name == "research_child"

    async def test_workflow_block_structure_with_mapping(self):
        """
        WorkflowBlock with input/output mappings should parse and structure correctly.
        Tests the parsing and schema integration without requiring Workflow.run() enhancement.
        """
        # Child workflow with interface declaring its public contract
        child_dict = {
            "version": "1.0",
            "id": "child",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": {
                "inputs": [{"name": "data", "target": "shared_memory.data"}],
                "outputs": [{"name": "task", "source": "results.task"}],
            },
            "blocks": {"task": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {
                "name": "child",
                "entry": "task",
                "transitions": [{"from": "task", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("child", child_file)

        # Parent with input/output mapping using interface names
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "setup": {"type": "linear", "soul_ref": "researcher"},
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "child",
                    "inputs": {"data": "shared_memory.parent_data"},
                    "outputs": {"results.child_output": "task"},
                },
            },
            "workflow": {
                "name": "parent",
                "entry": "setup",
                "transitions": [
                    {"from": "setup", "to": "invoke"},
                    {"from": "invoke", "to": None},
                ],
            },
        }

        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        # Verify WorkflowBlock was created with correct mappings
        block = parent_wf._blocks["invoke"]
        assert isinstance(block, WorkflowBlock)
        assert block.inputs == {"data": "shared_memory.parent_data"}
        assert block.outputs == {"results.child_output": "task"}
        assert block.child_workflow.name == "child"

    async def test_workflow_block_with_multiple_mappings(self):
        """
        WorkflowBlock with multiple input/output mappings should structure correctly.
        """
        # Child with interface declaring all inputs and outputs
        child_dict = {
            "version": "1.0",
            "id": "child-c",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": {
                "inputs": [
                    {"name": "input1", "target": "shared_memory.input1"},
                    {"name": "input2", "target": "shared_memory.input2"},
                    {"name": "input3", "target": "results.input3"},
                ],
                "outputs": [
                    {"name": "child_out1", "source": "results.child_out1"},
                    {"name": "child_out2", "source": "results.child_out2"},
                ],
            },
            "blocks": {"s": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {"name": "c", "entry": "s", "transitions": [{"from": "s", "to": None}]},
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("c", child_file)

        # Parent with multiple mappings using interface names
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "c",
                    "inputs": {
                        "input1": "shared_memory.parent1",
                        "input2": "shared_memory.parent2",
                        "input3": "results.parent_result",
                    },
                    "outputs": {
                        "results.out1": "child_out1",
                        "results.out2": "child_out2",
                    },
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)
        block = parent_wf._blocks["invoke"]

        # Verify all mappings are captured
        assert len(block.inputs) == 3
        assert len(block.outputs) == 2
        assert block.inputs["input1"] == "shared_memory.parent1"
        assert block.outputs["results.out1"] == "child_out1"


@pytest.mark.asyncio
class TestWorkflowBlockErrorHandling:
    """Test error handling at integration boundaries."""

    async def test_missing_workflow_ref_in_registry_raises(self):
        """Parser should raise when workflow_ref cannot be resolved."""
        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "nonexistent_child",
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        registry = WorkflowRegistry()
        # Don't register anything

        with pytest.raises(ValueError):
            parse_workflow_yaml(parent_dict, workflow_registry=registry)

    async def test_invalid_input_mapping_path_raises_at_runtime(self):
        """Invalid input path should raise at execution time."""
        # Child that expects input — must declare interface so the parent can bind to it
        child_dict = {
            "version": "1.0",
            "id": "child-c",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "interface": {
                "inputs": [{"name": "input", "target": "shared_memory.input"}],
                "outputs": [],
            },
            "blocks": {"s": {"type": "linear", "soul_ref": "researcher"}},
            "workflow": {"name": "c", "entry": "s", "transitions": [{"from": "s", "to": None}]},
        }
        child_file = RunsightWorkflowFile.model_validate(child_dict)

        registry = WorkflowRegistry()
        registry.register("c", child_file)

        parent_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "invoke": {
                    "type": "workflow",
                    "workflow_ref": "c",
                    "inputs": {
                        "input": "shared_memory.nonexistent_key",
                    },
                }
            },
            "workflow": {
                "name": "p",
                "entry": "invoke",
                "transitions": [{"from": "invoke", "to": None}],
            },
        }

        parent_wf = parse_workflow_yaml(parent_dict, workflow_registry=registry)

        # Execution should raise because input path doesn't exist
        initial_state = WorkflowState()  # No shared_memory.nonexistent_key

        with pytest.raises(KeyError):
            await parent_wf.run(initial_state)

    async def test_cycle_detection_in_workflow_block_execute(self):
        """
        Test that cycle detection is handled by WorkflowBlock.execute via call_stack.

        Note: This is tested in test_workflow_block_recursion.py with mocked workflows
        to avoid parser recursion issues. This test documents the integration point.
        """
        # Cycle detection is implemented in WorkflowBlock.execute() line 1076
        # and tested in test_workflow_block_recursion.py::test_cycle_detection_direct
        pass

    async def test_depth_limit_in_workflow_block_execute(self):
        """
        Test that depth limits are enforced by WorkflowBlock.execute via max_depth.

        Note: This is tested in test_workflow_block_recursion.py with mocked workflows
        to avoid parser recursion issues. This test documents the integration point.
        """
        # Depth limit enforcement is in WorkflowBlock.execute() line 1084
        # and tested in test_workflow_block_recursion.py::test_depth_limit
        pass


class TestBackwardCompatibility:
    """Test that existing features still work after merge."""

    def test_parse_simple_workflow_without_workflow_blocks(self):
        """Workflows without workflow blocks should parse normally."""
        yaml_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "step1": {"type": "linear", "soul_ref": "researcher"},
            },
            "workflow": {
                "name": "simple",
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }

        wf = parse_workflow_yaml(yaml_dict)
        assert wf.name == "simple"
        assert "step1" in wf._blocks

    @pytest.mark.asyncio
    async def test_execute_simple_workflow_without_registry(self):
        """Simple workflows should execute without registry parameter."""
        yaml_dict = {
            "version": "1.0",
            "id": "test-workflow",
            "kind": "workflow",
            "blocks": {
                "step1": {"type": "code", "code": "def main(data):\n    return {'step1': 'done'}"},
            },
            "workflow": {
                "name": "simple",
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }

        wf = parse_workflow_yaml(yaml_dict)
        state = WorkflowState()

        # Should work without workflow_registry parameter
        result = await wf.run(state)
        assert isinstance(result, WorkflowState)

    def test_all_original_block_types_still_work(self):
        """All original block types should still parse."""
        yaml_str = """
version: "1.0"
id: test-workflow
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Researcher
    role: Senior Researcher
    system_prompt: You research topics.
workflow:
  name: full_test
  entry: linear_step
blocks:
  linear_step:
    type: linear
    soul_ref: researcher
  final_step:
    type: linear
    soul_ref: researcher
transitions:
  - from: linear_step
    to: final_step
  - from: final_step
    to: null
"""
        wf = parse_workflow_yaml(yaml_str)
        assert "linear_step" in wf._blocks
        assert "final_step" in wf._blocks


# ---------------------------------------------------------------------------
# Helpers for external-soul-file tests
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to disk so parse_workflow_yaml infers workflow_base_dir."""
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(base_dir: Path, name: str, *, soul_id: str, role: str, prompt: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        dedent(f"""\
        id: {soul_id}
        kind: soul
        name: {soul_id.capitalize()}
        role: {role}
        system_prompt: {prompt}
        """),
        encoding="utf-8",
    )


class TestExternalSoulFileResolution:
    """Tests cover external soul file resolution (filesystem-based discovery).

    These complement the inline-soul tests above by exercising the
    _discover_external_souls() path: the parser is given a YAML *file path*
    so it can infer workflow_base_dir and scan custom/souls/*.yaml.
    """

    def test_external_soul_resolves_for_simple_workflow(self):
        """Workflow with soul_ref resolved from an external soul file should parse."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "researcher",
                soul_id="researcher",
                role="Senior Researcher",
                prompt="You research topics.",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                id: test-workflow
                kind: workflow
                blocks:
                  step1:
                    type: linear
                    soul_ref: researcher
                workflow:
                  name: simple
                  entry: step1
                  transitions:
                    - from: step1
                      to: null
                """,
            )

            wf = parse_workflow_yaml(path)
            assert wf.name == "simple"
            assert "step1" in wf._blocks

    def test_external_soul_resolves_for_workflow_with_registry(self):
        """Parser resolves child workflow AND external soul when given a file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "researcher",
                soul_id="researcher",
                role="Senior Researcher",
                prompt="You research topics.",
            )

            # Register child workflow in-memory (interface required + matched to parent bindings)
            child_dict = {
                "version": "1.0",
                "id": "analysis-child",
                "kind": "workflow",
                "souls": _RESEARCHER_SOUL,
                "interface": {
                    "inputs": [{"name": "topic", "target": "shared_memory.topic"}],
                    "outputs": [{"name": "output", "source": "results.output"}],
                },
                "blocks": {"step1": {"type": "linear", "soul_ref": "researcher"}},
                "workflow": {
                    "name": "analysis_child",
                    "entry": "step1",
                    "transitions": [{"from": "step1", "to": None}],
                },
            }
            child_file = RunsightWorkflowFile.model_validate(child_dict)
            registry = WorkflowRegistry()
            registry.register("analysis_child", child_file)

            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                id: test-workflow
                kind: workflow
                blocks:
                  invoke_analysis:
                    type: workflow
                    workflow_ref: analysis_child
                    inputs:
                      topic: shared_memory.input_topic
                    outputs:
                      results.analysis: output
                workflow:
                  name: main_workflow
                  entry: invoke_analysis
                  transitions:
                    - from: invoke_analysis
                      to: null
                """,
            )

            parent_wf = parse_workflow_yaml(path, workflow_registry=registry)

            assert isinstance(parent_wf, Workflow)
            assert "invoke_analysis" in parent_wf._blocks
            block = parent_wf._blocks["invoke_analysis"]
            assert isinstance(block, WorkflowBlock)
            assert block.child_workflow.name == "analysis_child"

    def test_external_soul_resolves_all_original_block_types(self):
        """All original block types parse when soul comes from external file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "researcher",
                soul_id="researcher",
                role="Senior Researcher",
                prompt="You research topics.",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                id: test-workflow
                kind: workflow
                blocks:
                  linear_step:
                    type: linear
                    soul_ref: researcher
                  final_step:
                    type: linear
                    soul_ref: researcher
                workflow:
                  name: full_test
                  entry: linear_step
                  transitions:
                    - from: linear_step
                      to: final_step
                    - from: final_step
                      to: null
                """,
            )

            wf = parse_workflow_yaml(path)
            assert "linear_step" in wf._blocks
            assert "final_step" in wf._blocks
