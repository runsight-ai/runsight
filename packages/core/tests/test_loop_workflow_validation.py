"""
Regression tests for workflow blocks nested inside LoopBlock inner refs.

These tests pin the currently supported runtime behavior:
- top-level workflow blocks are allowed
- loop.inner_block_refs may point at workflow blocks
- recursive workflow-call validation should accept the placement
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import yaml
from runsight_core.yaml.discovery import WorkflowScanner
from runsight_core.yaml.parser import (
    parse_workflow_yaml,
    validate_workflow_call_contracts,
)
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _code_workflow(name: str, *, entry: str = "step") -> dict:
    return {
        "version": "1.0",
        "id": name,
        "kind": "workflow",
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


def test_parse_workflow_yaml_allows_loop_referencing_workflow_block() -> None:
    """Workflow blocks remain valid both at top level and inside a loop."""
    child_file = RunsightWorkflowFile.model_validate(_code_workflow("child_workflow"))
    registry = WorkflowRegistry()
    registry.register("child_workflow", child_file)

    allowed_parent = {
        "version": "1.0",
        "id": "allowed_parent",
        "kind": "workflow",
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
        "id": "nested_parent",
        "kind": "workflow",
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

    wf = parse_workflow_yaml(nested_parent, workflow_registry=registry)
    assert wf.blocks["call_child"].workflow_ref == "child_workflow"


def test_validate_workflow_call_contracts_allows_nested_loop_workflow_recursively(
    tmp_path: Path,
) -> None:
    """Recursive workflow-call validation should accept nested loop workflow refs."""
    parent_path = tmp_path / "custom" / "workflows" / "parent_workflow.yaml"
    child_path = tmp_path / "custom" / "workflows" / "child_workflow.yaml"
    grandchild_path = tmp_path / "custom" / "workflows" / "grandchild_workflow.yaml"

    grandchild_data = _code_workflow("grandchild_workflow")
    child_data = {
        "version": "1.0",
        "id": "child_workflow",
        "kind": "workflow",
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
        "id": "parent_workflow",
        "kind": "workflow",
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

    scan_index = WorkflowScanner(str(tmp_path)).scan()
    validation_index = {
        result.entity_id: (result.path, result.item)
        for result in scan_index.get_all()
        if result.entity_id is not None
    }
    parent_file = RunsightWorkflowFile.model_validate(parent_data)

    validate_workflow_call_contracts(
        parent_file,
        base_dir=str(tmp_path),
        validation_index=validation_index,
        current_workflow_ref=str(parent_path),
    )
