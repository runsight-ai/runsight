"""WorkflowBlock-in-LoopBlock validation behavior.

These tests cover the supported workflow-call validation boundary:
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


def _code_workflow(name: str, *, entry: str = "workflow_code_step") -> dict:
    return {
        "version": "1.0",
        "id": name,
        "kind": "workflow",
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
    callable_workflow_ref = "loop_callable_workflow"
    child_file = RunsightWorkflowFile.model_validate(
        _code_workflow(callable_workflow_ref, entry="callable_workflow_code_step")
    )
    registry = WorkflowRegistry()
    registry.register(callable_workflow_ref, child_file)

    top_level_workflow_caller = {
        "version": "1.0",
        "id": "top_level_workflow_caller",
        "kind": "workflow",
        "blocks": {
            "call_workflow_directly": {
                "type": "workflow",
                "workflow_ref": callable_workflow_ref,
            }
        },
        "workflow": {
            "name": "top_level_workflow_caller",
            "entry": "call_workflow_directly",
            "transitions": [
                {
                    "from": "call_workflow_directly",
                    "to": None,
                }
            ],
        },
    }

    wf = parse_workflow_yaml(top_level_workflow_caller, workflow_registry=registry)
    assert wf.blocks["call_workflow_directly"].workflow_ref == callable_workflow_ref

    loop_inner_workflow_caller = {
        "version": "1.0",
        "id": "loop_inner_workflow_caller",
        "kind": "workflow",
        "blocks": {
            "call_workflow_from_loop": {
                "type": "workflow",
                "workflow_ref": callable_workflow_ref,
            },
            "workflow_call_loop": {
                "type": "loop",
                "inner_block_refs": ["call_workflow_from_loop"],
                "max_rounds": 1,
            },
        },
        "workflow": {
            "name": "loop_inner_workflow_caller",
            "entry": "call_workflow_from_loop",
            "transitions": [
                {
                    "from": "call_workflow_from_loop",
                    "to": "workflow_call_loop",
                },
                {
                    "from": "workflow_call_loop",
                    "to": None,
                },
            ],
        },
    }

    wf = parse_workflow_yaml(loop_inner_workflow_caller, workflow_registry=registry)
    assert wf.blocks["call_workflow_from_loop"].workflow_ref == callable_workflow_ref


def test_validate_workflow_call_contracts_allows_nested_loop_workflow_recursively(
    tmp_path: Path,
) -> None:
    """Recursive workflow-call validation should accept nested loop workflow refs."""
    parent_path = tmp_path / "custom" / "workflows" / "recursive_contract_root.yaml"
    child_path = tmp_path / "custom" / "workflows" / "loop_contract_child.yaml"
    grandchild_path = tmp_path / "custom" / "workflows" / "loop_contract_leaf.yaml"

    grandchild_data = _code_workflow("loop_contract_leaf", entry="leaf_contract_code_step")
    child_data = {
        "version": "1.0",
        "id": "loop_contract_child",
        "kind": "workflow",
        "blocks": {
            "call_leaf_from_loop": {
                "type": "workflow",
                "workflow_ref": "loop_contract_leaf",
            },
            "recursive_validation_loop": {
                "type": "loop",
                "inner_block_refs": ["call_leaf_from_loop"],
                "max_rounds": 1,
            },
        },
        "workflow": {
            "name": "loop_contract_child",
            "entry": "recursive_validation_loop",
            "transitions": [
                {
                    "from": "recursive_validation_loop",
                    "to": None,
                }
            ],
        },
    }
    parent_data = {
        "version": "1.0",
        "id": "recursive_contract_root",
        "kind": "workflow",
        "blocks": {
            "enter_loop_child_contract": {
                "type": "workflow",
                "workflow_ref": "loop_contract_child",
            }
        },
        "workflow": {
            "name": "recursive_contract_root",
            "entry": "enter_loop_child_contract",
            "transitions": [
                {
                    "from": "enter_loop_child_contract",
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
