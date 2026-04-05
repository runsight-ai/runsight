"""
Red tests for rejecting workflow blocks nested inside LoopBlock inner refs.

These tests pin the missing validation boundary:
- top-level workflow blocks remain allowed
- loop.inner_block_refs must not point at workflow blocks
- the prohibition must hold recursively through child workflow contracts
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from runsight_core.yaml.parser import (
    _build_workflow_validation_index,
    parse_workflow_yaml,
    validate_workflow_call_contracts,
)
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _code_workflow(name: str, *, entry: str = "step") -> dict:
    return {
        "version": "1.0",
        "interface": {
            "inputs": [],
            "outputs": [],
        },
        "blocks": {
            entry: {
                "type": "code",
                "code": dedent(
                    """\
                    def main(data):
                        return {}
                    """
                ),
            }
        },
        "workflow": {
            "name": name,
            "entry": entry,
            "transitions": [
                {
                    "from": entry,
                    "to": None,
                }
            ],
        },
    }


def _write_workflow_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_parse_workflow_yaml_rejects_loop_referencing_workflow_block() -> None:
    """A workflow block at top level stays allowed, but not inside a loop."""
    child_file = RunsightWorkflowFile.model_validate(_code_workflow("child_workflow"))
    registry = WorkflowRegistry()
    registry.register("child_workflow", child_file)

    allowed_parent = {
        "version": "1.0",
        "blocks": {
            "call_child": {
                "type": "workflow",
                "workflow_ref": "child_workflow",
            }
        },
        "workflow": {
            "name": "allowed_parent",
            "entry": "call_child",
            "transitions": [
                {
                    "from": "call_child",
                    "to": None,
                }
            ],
        },
    }

    wf = parse_workflow_yaml(allowed_parent, workflow_registry=registry)
    assert wf.blocks["call_child"].workflow_ref == "child_workflow"

    nested_parent = {
        "version": "1.0",
        "blocks": {
            "call_child": {
                "type": "workflow",
                "workflow_ref": "child_workflow",
            },
            "loop_block": {
                "type": "loop",
                "inner_block_refs": ["call_child"],
                "max_rounds": 1,
            },
        },
        "workflow": {
            "name": "nested_parent",
            "entry": "call_child",
            "transitions": [
                {
                    "from": "call_child",
                    "to": "loop_block",
                },
                {
                    "from": "loop_block",
                    "to": None,
                },
            ],
        },
    }

    with pytest.raises(ValueError, match=r"loop_block.*call_child.*unsupported"):
        parse_workflow_yaml(nested_parent, workflow_registry=registry)


def test_validate_workflow_call_contracts_rejects_nested_loop_workflow_recursively(
    tmp_path: Path,
) -> None:
    """Recursive workflow-call validation must reject a child loop that names a workflow block."""
    parent_path = tmp_path / "custom" / "workflows" / "parent.yaml"
    child_path = tmp_path / "custom" / "workflows" / "child.yaml"
    grandchild_path = tmp_path / "custom" / "workflows" / "grandchild.yaml"

    grandchild_data = _code_workflow("grandchild_workflow")
    child_data = {
        "version": "1.0",
        "interface": {
            "inputs": [],
            "outputs": [],
        },
        "blocks": {
            "invoke_grandchild": {
                "type": "workflow",
                "workflow_ref": "grandchild_workflow",
            },
            "loop_block": {
                "type": "loop",
                "inner_block_refs": ["invoke_grandchild"],
                "max_rounds": 1,
            },
        },
        "workflow": {
            "name": "child_workflow",
            "entry": "loop_block",
            "transitions": [
                {
                    "from": "loop_block",
                    "to": None,
                }
            ],
        },
    }
    parent_data = {
        "version": "1.0",
        "blocks": {
            "invoke_child": {
                "type": "workflow",
                "workflow_ref": "child_workflow",
            }
        },
        "workflow": {
            "name": "parent_workflow",
            "entry": "invoke_child",
            "transitions": [
                {
                    "from": "invoke_child",
                    "to": None,
                }
            ],
        },
    }

    _write_workflow_file(grandchild_path, grandchild_data)
    _write_workflow_file(child_path, child_data)
    _write_workflow_file(parent_path, parent_data)

    validation_index = _build_workflow_validation_index(str(tmp_path))
    parent_file = RunsightWorkflowFile.model_validate(parent_data)

    with pytest.raises(ValueError, match=r"loop_block.*invoke_grandchild.*unsupported"):
        validate_workflow_call_contracts(
            parent_file,
            base_dir=str(tmp_path),
            validation_index=validation_index,
            current_workflow_ref=str(parent_path),
            allow_filesystem_fallback=False,
        )
