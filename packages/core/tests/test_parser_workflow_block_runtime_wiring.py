"""
Tests for YAML Parser integration with WorkflowBlock.

This module tests:
- Parsing YAML with type: workflow blocks
- WorkflowRegistry parameter validation
- Special-case handler for workflow blocks (placed before BLOCK_TYPE_REGISTRY lookup)
- Input/output mapping configuration
- max_depth resolution from block-level or global config
- snapshot discovery context forwarding for nested workflow parses
"""

import pytest
from runsight_core import LoopBlock, WorkflowBlock
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile

_RESEARCHER_SOUL = {
    "researcher": {
        "id": "researcher",
        "kind": "soul",
        "name": "Senior Researcher",
        "role": "Senior Researcher",
        "system_prompt": "You research topics.",
    }
}


def _with_workflow_identity(raw: dict, workflow_id: str) -> dict:
    raw.setdefault("id", workflow_id)
    raw.setdefault("kind", "workflow")
    workflow = raw.setdefault("workflow", {})
    workflow.setdefault("id", workflow_id)
    workflow.setdefault("kind", "workflow")
    workflow.setdefault("name", workflow_id)
    return raw


class TestParseWorkflowBlock:
    """Tests for parsing workflow blocks from YAML."""

    def test_parse_loopblock_with_workflow_block_inner_ref_resolves_child_workflow(self):
        """LoopBlock should preserve WorkflowBlock refs and the parser should resolve the invoked workflow."""
        invoked_workflow_yaml = {
            "version": "1.0",
            "id": "parser_invoked_workflow",
            "kind": "workflow",
            "blocks": {
                "parser_invoked_step": {
                    "type": "code",
                    "code": "def main(data):\n    return {'parser_invoked_step': 'done'}",
                }
            },
            "workflow": {
                "id": "parser_invoked_workflow",
                "kind": "workflow",
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        caller_workflow_yaml = {
            "version": "1.0",
            "id": "workflow_block_parser_workflow",
            "kind": "workflow",
            "blocks": {
                "loop_workflow_call": {
                    "type": "loop",
                    "inner_block_refs": ["call_parser_invoked_workflow"],
                    "max_rounds": 2,
                },
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                },
            },
            "workflow": {
                "id": "workflow_block_parser_workflow",
                "kind": "workflow",
                "name": "workflow_block_parser_workflow",
                "entry": "loop_workflow_call",
                "transitions": [{"from": "loop_workflow_call", "to": None}],
            },
        }

        workflow_block_parser_workflow = parse_workflow_yaml(
            _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
            workflow_registry=registry,
        )

        assert isinstance(workflow_block_parser_workflow, Workflow)
        loop_block = workflow_block_parser_workflow.blocks["loop_workflow_call"]
        workflow_block = workflow_block_parser_workflow.blocks["call_parser_invoked_workflow"]

        assert isinstance(loop_block, LoopBlock)
        assert loop_block.inner_block_refs == ["call_parser_invoked_workflow"]
        assert isinstance(workflow_block, WorkflowBlock)
        assert workflow_block.block_id == "call_parser_invoked_workflow"
        assert workflow_block.workflow_ref == "parser_invoked_workflow"
        assert workflow_block.child_workflow.name == "parser_invoked_workflow"

    def test_exit_conditions_bridged_from_schema_to_runtime_block(self):
        """Parser should copy exit_conditions from BaseBlockDef to runtime BaseBlock."""
        yaml_dict = {
            "version": "1.0",
            "id": "exit_cond_test",
            "kind": "workflow",
            "blocks": {
                "evaluator": {
                    "type": "code",
                    "code": "def main(data):\n    return {'result': 'ok'}",
                    "exit_conditions": [
                        {"contains": "PASS", "exit_handle": "pass"},
                        {"regex": "score:\\s*\\d+", "exit_handle": "scored"},
                    ],
                },
            },
            "workflow": {
                "id": "exit_cond_test",
                "kind": "workflow",
                "name": "exit_cond_test",
                "entry": "evaluator",
                "transitions": [{"from": "evaluator", "to": None}],
            },
        }

        workflow = parse_workflow_yaml(_with_workflow_identity(yaml_dict, "simple_workflow"))
        block = workflow.blocks["evaluator"]

        assert block.exit_conditions is not None
        assert len(block.exit_conditions) == 2
        assert block.exit_conditions[0].contains == "PASS"
        assert block.exit_conditions[0].exit_handle == "pass"
        assert block.exit_conditions[1].regex == "score:\\s*\\d+"
        assert block.exit_conditions[1].exit_handle == "scored"

    def test_parse_workflow_with_workflow_block(self):
        """
        Parser creates WorkflowBlock from YAML with registry.

        Verify:
        - YAML with type: workflow block parses successfully
        - Returned Workflow contains a WorkflowBlock instance
        - WorkflowBlock.child_workflow.name matches workflow_ref
        - Input/output mappings are correctly set
        """
        # Create and register invoked workflow
        invoked_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "inputs": {"topic": {"type": "string"}},
            "blocks": {
                "parser_invoked_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        # Set up registry with invoked workflow
        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        # Create caller YAML with workflow block
        caller_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                    "inputs": {"topic": "shared_memory.research_topic"},
                    "outputs": {"results.invoked_result": "results.parser_invoked_step"},
                },
                "final_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [
                    {"from": "call_parser_invoked_workflow", "to": "final_step"},
                    {"from": "final_step", "to": None},
                ],
            },
        }

        # Parse caller workflow with registry
        workflow_block_parser_workflow = parse_workflow_yaml(
            _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
            workflow_registry=registry,
        )

        # Assert Workflow is valid
        assert isinstance(workflow_block_parser_workflow, Workflow)
        assert workflow_block_parser_workflow.name == "workflow_block_parser_workflow"

        # Assert workflow contains WorkflowBlock instance
        assert "call_parser_invoked_workflow" in workflow_block_parser_workflow._blocks
        workflow_block = workflow_block_parser_workflow._blocks["call_parser_invoked_workflow"]
        assert isinstance(workflow_block, WorkflowBlock)

        # Assert WorkflowBlock has correct invoked workflow
        assert workflow_block.child_workflow.name == "parser_invoked_workflow"

        # Assert name-based invocation mappings are correctly set
        assert workflow_block.inputs == {"topic": "shared_memory.research_topic"}
        assert workflow_block.outputs == {"results.invoked_result": "results.parser_invoked_step"}

    def test_parse_workflow_block_forwards_snapshot_discovery_context_to_child_parse(self):
        """Nested workflow parsing must preserve explicit snapshot discovery context."""
        import runsight_core.yaml.parser as parser_module

        invoked_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "parser_invoked_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        caller_workflow_yaml = {
            "version": "1.0",
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [{"from": "call_parser_invoked_workflow", "to": None}],
            },
        }

        original_parse = parser_module.parse_workflow_yaml
        invoked_parse_calls: list[dict[str, object]] = []
        git_service = type("GitServiceDouble", (), {"repo_path": "."})()

        def _record_invoked_parse(*args, **kwargs):
            invoked_parse_calls.append(kwargs)
            return original_parse(*args, **kwargs)

        from unittest.mock import patch

        with (
            patch.object(parser_module, "parse_workflow_yaml", side_effect=_record_invoked_parse),
            patch.object(parser_module.AssertionScanner, "scan") as mock_assertion_scan,
            patch.object(parser_module.SoulScanner, "scan") as mock_soul_scan,
            patch.object(parser_module.ToolScanner, "scan") as mock_tool_scan,
        ):
            mock_assertion_scan.return_value.ids.return_value = {}
            mock_soul_scan.return_value.ids.return_value = {}
            mock_tool_scan.return_value.ids.return_value = {}

            workflow_block_parser_workflow = original_parse(
                _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
                workflow_registry=registry,
                _discovery_git_ref="main",
                _discovery_git_service=git_service,
            )

        assert isinstance(
            workflow_block_parser_workflow._blocks["call_parser_invoked_workflow"], WorkflowBlock
        )
        assert len(invoked_parse_calls) == 1
        assert invoked_parse_calls[0]["_discovery_git_ref"] == "main"
        assert invoked_parse_calls[0]["_discovery_git_service"] is git_service

    def test_parse_workflow_block_no_registry_raises(self):
        """
        Parser raises clear error when registry absent for workflow block.

        Verify:
        - Calling parse_workflow_yaml() with type: workflow block but no registry
        - Raises ValueError with clear message
        - Error message contains "WorkflowRegistry must be provided"
        """
        # Create YAML with workflow block
        yaml_dict = {
            "version": "1.0",
            "id": "workflow_block_parser_workflow",
            "kind": "workflow",
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [{"from": "call_parser_invoked_workflow", "to": None}],
            },
        }

        # Attempt to parse without registry (workflow_registry=None by default)
        with pytest.raises(ValueError) as exc_info:
            parse_workflow_yaml(_with_workflow_identity(yaml_dict, "simple_workflow"))

        # Verify error message
        error_msg = str(exc_info.value).lower()
        assert "workflowregistry" in error_msg or "registry" in error_msg
        assert "provided" in error_msg or "required" in error_msg

    def test_parse_workflow_block_max_depth_block_level(self):
        """
        Verify max_depth is read from block-level config when present.

        Create workflow block with explicit max_depth, verify WorkflowBlock.max_depth is set.
        """
        # Create and register invoked workflow
        invoked_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "parser_invoked_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        # Create caller with block-level max_depth
        caller_workflow_yaml = {
            "version": "1.0",
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                    "max_depth": 5,
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [{"from": "call_parser_invoked_workflow", "to": None}],
            },
        }

        workflow_block_parser_workflow = parse_workflow_yaml(
            _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
            workflow_registry=registry,
        )

        workflow_block = workflow_block_parser_workflow._blocks["call_parser_invoked_workflow"]
        assert workflow_block.max_depth == 5

    def test_parse_workflow_block_max_depth_global_config(self):
        """
        Verify max_depth falls back to global config when block-level not set.

        Create workflow with global max_workflow_depth config, no block-level max_depth.
        Verify WorkflowBlock.max_depth uses global config.
        """
        # Create and register invoked workflow
        invoked_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "parser_invoked_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        # Create caller with global max_workflow_depth config
        caller_workflow_yaml = {
            "version": "1.0",
            "config": {
                "max_workflow_depth": 7,
            },
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                    # No max_depth at block level
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [{"from": "call_parser_invoked_workflow", "to": None}],
            },
        }

        workflow_block_parser_workflow = parse_workflow_yaml(
            _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
            workflow_registry=registry,
        )

        workflow_block = workflow_block_parser_workflow._blocks["call_parser_invoked_workflow"]
        assert workflow_block.max_depth == 7

    def test_parse_workflow_block_max_depth_default(self):
        """
        Verify max_depth defaults to 10 when neither block-level nor global config set.
        """
        # Create and register invoked workflow
        invoked_workflow_yaml = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "parser_invoked_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "parser_invoked_workflow",
                "entry": "parser_invoked_step",
                "transitions": [{"from": "parser_invoked_step", "to": None}],
            },
        }
        invoked_workflow_file = RunsightWorkflowFile.model_validate(
            _with_workflow_identity(invoked_workflow_yaml, "parser_invoked_workflow")
        )

        registry = WorkflowRegistry()
        registry.register("parser_invoked_workflow", invoked_workflow_file)

        # Create caller without max_depth at any level
        caller_workflow_yaml = {
            "version": "1.0",
            "blocks": {
                "call_parser_invoked_workflow": {
                    "type": "workflow",
                    "workflow_ref": "parser_invoked_workflow",
                },
            },
            "workflow": {
                "name": "workflow_block_parser_workflow",
                "entry": "call_parser_invoked_workflow",
                "transitions": [{"from": "call_parser_invoked_workflow", "to": None}],
            },
        }

        workflow_block_parser_workflow = parse_workflow_yaml(
            _with_workflow_identity(caller_workflow_yaml, "workflow_block_parser_workflow"),
            workflow_registry=registry,
        )

        workflow_block = workflow_block_parser_workflow._blocks["call_parser_invoked_workflow"]
        assert workflow_block.max_depth == 10  # default

    def test_parse_workflow_no_registry_no_workflow_blocks(self):
        """
        Parser backward-compatible — no registry needed for non-workflow YAML.

        Verify:
        - Parsing standard YAML (no workflow blocks) without registry succeeds
        - Backward compatibility maintained
        """
        # Create simple workflow without workflow blocks
        yaml_dict = {
            "version": "1.0",
            "souls": _RESEARCHER_SOUL,
            "blocks": {
                "solo_linear_step": {
                    "type": "linear",
                    "soul_ref": "researcher",
                },
            },
            "workflow": {
                "name": "simple_workflow",
                "entry": "solo_linear_step",
                "transitions": [{"from": "solo_linear_step", "to": None}],
            },
        }

        # Parse without registry (workflow_registry=None by default)
        workflow = parse_workflow_yaml(_with_workflow_identity(yaml_dict, "simple_workflow"))

        # Verify parsing succeeds
        assert isinstance(workflow, Workflow)
        assert workflow.name == "simple_workflow"
        assert "solo_linear_step" in workflow._blocks
