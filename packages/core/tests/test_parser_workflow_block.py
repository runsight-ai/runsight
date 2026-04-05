"""
Tests for YAML Parser integration with WorkflowBlock.

This module tests:
- Parsing YAML with type: workflow blocks
- WorkflowRegistry parameter validation
- Special-case handler for workflow blocks (placed before BLOCK_TYPE_REGISTRY lookup)
- Input/output mapping configuration
- max_depth resolution from block-level or global config
"""

import pytest
from runsight_core import LoopBlock, WorkflowBlock
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile

_RESEARCHER_SOUL = {
    "researcher": {
        "id": "researcher_1",
        "role": "Senior Researcher",
        "system_prompt": "You research topics.",
    }
}


class TestParseWorkflowBlock:
    """Tests for parsing workflow blocks from YAML."""

    def test_parse_loopblock_with_workflow_block_inner_ref_resolves_child_workflow(self):
        """LoopBlock should preserve WorkflowBlock refs and the parser should resolve the child."""
        child_yaml_dict = {
            "version": "1.0",
            "interface": {
                "inputs": [],
                "outputs": [
                    {
                        "name": "done",
                        "source": "results.child_step",
                    }
                ],
            },
            "blocks": {
                "child_step": {
                    "type": "code",
                    "code": "def main(data):\n    return {'child_step': 'done'}",
                }
            },
            "workflow": {
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml_dict)

        registry = WorkflowRegistry(allow_filesystem_fallback=False)
        registry.register("child_workflow", child_file)

        parent_yaml_dict = {
            "version": "1.0",
            "blocks": {
                "loop_step": {
                    "type": "loop",
                    "inner_block_refs": ["invoke_child"],
                    "max_rounds": 2,
                },
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    "outputs": {"results.child_summary": "done"},
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "loop_step",
                "transitions": [{"from": "loop_step", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_yaml_dict, workflow_registry=registry)

        assert isinstance(parent_workflow, Workflow)
        loop_block = parent_workflow.blocks["loop_step"]
        workflow_block = parent_workflow.blocks["invoke_child"]

        assert isinstance(loop_block, LoopBlock)
        assert loop_block.inner_block_refs == ["invoke_child"]
        assert isinstance(workflow_block, WorkflowBlock)
        assert workflow_block.block_id == "invoke_child"
        assert workflow_block.workflow_ref == "child_workflow"
        assert workflow_block.child_workflow.name == "child_workflow"

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_workflow_with_workflow_block(self):
        """
        AC-14: Parser creates WorkflowBlock from YAML with registry.

        Verify:
        - YAML with type: workflow block parses successfully
        - Returned Workflow contains a WorkflowBlock instance
        - WorkflowBlock.child_workflow.name matches workflow_ref
        - Input/output mappings are correctly set
        """
        # Create and register child workflow
        child_yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "child_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml_dict)

        # Set up registry with child workflow
        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        # Create parent YAML with workflow block
        parent_yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    "inputs": {"shared_memory.topic": "shared_memory.research_topic"},
                    "outputs": {"results.child_result": "results.child_step"},
                },
                "final_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [
                    {"from": "invoke_child", "to": "final_step"},
                    {"from": "final_step", "to": None},
                ],
            },
        }

        # Parse parent workflow with registry
        parent_workflow = parse_workflow_yaml(parent_yaml_dict, workflow_registry=registry)

        # Assert Workflow is valid
        assert isinstance(parent_workflow, Workflow)
        assert parent_workflow.name == "parent_workflow"

        # Assert workflow contains WorkflowBlock instance
        assert "invoke_child" in parent_workflow._blocks
        workflow_block = parent_workflow._blocks["invoke_child"]
        assert isinstance(workflow_block, WorkflowBlock)

        # Assert WorkflowBlock has correct child workflow
        assert workflow_block.child_workflow.name == "child_workflow"

        # Assert input/output mappings are correctly set
        assert workflow_block.inputs == {"shared_memory.topic": "shared_memory.research_topic"}
        assert workflow_block.outputs == {"results.child_result": "results.child_step"}

    def test_parse_workflow_block_no_registry_raises(self):
        """
        AC-15: Parser raises clear error when registry absent for workflow block.

        Verify:
        - Calling parse_workflow_yaml() with type: workflow block but no registry
        - Raises ValueError with clear message
        - Error message contains "WorkflowRegistry must be provided"
        """
        # Create YAML with workflow block
        yaml_dict = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        # Attempt to parse without registry (workflow_registry=None by default)
        with pytest.raises(ValueError) as exc_info:
            parse_workflow_yaml(yaml_dict)

        # Verify error message
        error_msg = str(exc_info.value).lower()
        assert "workflowregistry" in error_msg or "registry" in error_msg
        assert "provided" in error_msg or "required" in error_msg

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_workflow_block_max_depth_block_level(self):
        """
        Verify max_depth is read from block-level config when present.

        Create workflow block with explicit max_depth, verify WorkflowBlock.max_depth is set.
        """
        # Create and register child workflow
        child_yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "child_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml_dict)

        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        # Create parent with block-level max_depth
        parent_yaml_dict = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    "max_depth": 5,
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_yaml_dict, workflow_registry=registry)

        workflow_block = parent_workflow._blocks["invoke_child"]
        assert workflow_block.max_depth == 5

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_workflow_block_max_depth_global_config(self):
        """
        Verify max_depth falls back to global config when block-level not set.

        Create workflow with global max_workflow_depth config, no block-level max_depth.
        Verify WorkflowBlock.max_depth uses global config.
        """
        # Create and register child workflow
        child_yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "child_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml_dict)

        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        # Create parent with global max_workflow_depth config
        parent_yaml_dict = {
            "version": "1.0",
            "config": {
                "model_name": "gpt-4o",
                "max_workflow_depth": 7,
            },
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                    # No max_depth at block level
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_yaml_dict, workflow_registry=registry)

        workflow_block = parent_workflow._blocks["invoke_child"]
        assert workflow_block.max_depth == 7

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_workflow_block_max_depth_default(self):
        """
        Verify max_depth defaults to 10 when neither block-level nor global config set.
        """
        # Create and register child workflow
        child_yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "child_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "child_workflow",
                "entry": "child_step",
                "transitions": [{"from": "child_step", "to": None}],
            },
        }
        child_file = RunsightWorkflowFile.model_validate(child_yaml_dict)

        registry = WorkflowRegistry()
        registry.register("child_workflow", child_file)

        # Create parent without max_depth at any level
        parent_yaml_dict = {
            "version": "1.0",
            "blocks": {
                "invoke_child": {
                    "type": "workflow",
                    "workflow_ref": "child_workflow",
                },
            },
            "workflow": {
                "name": "parent_workflow",
                "entry": "invoke_child",
                "transitions": [{"from": "invoke_child", "to": None}],
            },
        }

        parent_workflow = parse_workflow_yaml(parent_yaml_dict, workflow_registry=registry)

        workflow_block = parent_workflow._blocks["invoke_child"]
        assert workflow_block.max_depth == 10  # default

    @pytest.mark.xfail(
        reason="RUN-570 removed inline souls; RUN-571 will wire library discovery", strict=True
    )
    def test_parse_workflow_no_registry_no_workflow_blocks(self):
        """
        AC-16: Parser backward-compatible — no registry needed for non-workflow YAML.

        Verify:
        - Parsing standard YAML (no workflow blocks) without registry succeeds
        - Backward compatibility maintained
        """
        # Create simple workflow without workflow blocks
        yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "step1": {
                    "type": "linear",
                    "soul_ref": "researcher",
                },
            },
            "workflow": {
                "name": "simple_workflow",
                "entry": "step1",
                "transitions": [{"from": "step1", "to": None}],
            },
        }

        # Parse without registry (workflow_registry=None by default)
        workflow = parse_workflow_yaml(yaml_dict)

        # Verify parsing succeeds
        assert isinstance(workflow, Workflow)
        assert workflow.name == "simple_workflow"
        assert "step1" in workflow._blocks
