"""
Tests for route workflow blocks through the registered builder.

These tests pin the workflow-block parser/builder path:
- parse_workflow_yaml should use the registered "workflow" builder, not a parser-only special case
- the registered builder should be able to construct a real WorkflowBlock when given parser context
- missing WorkflowRegistry should fail with an actionable ValueError from the builder path
- workflow blocks referenced from LoopBlock.inner_block_refs should still come through the builder path
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from runsight_core import LoopBlock, WorkflowBlock
from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY
from runsight_core.workflow import Workflow
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _child_workflow_file() -> RunsightWorkflowFile:
    child_dict = {
        "id": "builder-child-workflow",
        "kind": "workflow",
        "version": "1.0",
        "blocks": {
            "builder_child_step": {
                "type": "code",
                "code": "def main(data):\n    return {'builder_child_step': 'done'}",
            }
        },
        "workflow": {
            "name": "builder_child_workflow",
            "entry": "builder_child_step",
            "transitions": [{"from": "builder_child_step", "to": None}],
        },
    }
    return RunsightWorkflowFile.model_validate(child_dict)


def _parent_workflow_dict() -> dict[str, Any]:
    return {
        "id": "builder-parent-workflow",
        "kind": "workflow",
        "version": "1.0",
        "config": {
            "max_workflow_depth": 7,
        },
        "blocks": {
            "builder_child_workflow_block": {
                "type": "workflow",
                "workflow_ref": "builder-child-workflow",
            },
            "builder_loop_block": {
                "type": "loop",
                "inner_block_refs": ["builder_child_workflow_block"],
                "max_rounds": 1,
            },
        },
        "workflow": {
            "name": "builder_parent_workflow",
            "entry": "builder_child_workflow_block",
            "transitions": [
                {"from": "builder_child_workflow_block", "to": "builder_loop_block"},
                {"from": "builder_loop_block", "to": None},
            ],
        },
    }


def test_parse_workflow_yaml_routes_workflow_blocks_through_registered_builder_even_inside_loops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Parsing should invoke the registered workflow builder instead of a parser special case."""
    child_file = _child_workflow_file()
    registry = WorkflowRegistry()
    registry.register("builder-child-workflow", child_file)

    calls: list[dict[str, Any]] = []

    def spy_builder(
        block_id: str,
        block_def: Any,
        souls_map: dict[str, Any],
        runner: Any,
        all_blocks: dict[str, Any],
        **parser_context: Any,
    ) -> WorkflowBlock:
        calls.append(
            {
                "block_id": block_id,
                "block_def": block_def,
                "souls_map": souls_map,
                "runner": runner,
                "all_blocks": dict(all_blocks),
                "parser_context": parser_context,
            }
        )
        child_workflow = parse_workflow_yaml(
            child_file.model_dump(),
            workflow_registry=parser_context["workflow_registry"],
            api_keys=parser_context.get("api_keys"),
            _base_dir=parser_context["workflow_base_dir"],
        )
        parent_file_def = parser_context["parent_file_def"]
        max_depth = (
            block_def.max_depth
            if block_def.max_depth is not None
            else parent_file_def.config.get("max_workflow_depth", 10)
        )
        return WorkflowBlock(
            block_id=block_id,
            child_workflow=child_workflow,
            inputs=block_def.inputs or {},
            outputs=block_def.outputs or {},
            workflow_ref=block_def.workflow_ref,
            max_depth=max_depth,
            on_error=block_def.on_error,
        )

    monkeypatch.setitem(BLOCK_BUILDER_REGISTRY, "workflow", spy_builder)

    parent_workflow = parse_workflow_yaml(
        _parent_workflow_dict(),
        workflow_registry=registry,
        _base_dir=str(tmp_path),
    )

    assert calls, "parse_workflow_yaml did not call the registered workflow builder"
    assert isinstance(parent_workflow, Workflow)
    assert isinstance(parent_workflow.blocks["builder_child_workflow_block"], WorkflowBlock)
    assert (
        parent_workflow.blocks["builder_child_workflow_block"].child_workflow.name
        == "builder_child_workflow"
    )
    assert isinstance(parent_workflow.blocks["builder_loop_block"], LoopBlock)
    assert parent_workflow.blocks["builder_loop_block"].inner_block_refs == [
        "builder_child_workflow_block"
    ]


def test_registered_workflow_builder_accepts_parser_context_and_builds_real_workflow_block(
    tmp_path: Path,
) -> None:
    """The registered workflow builder should build a real WorkflowBlock with parser context."""
    child_file = _child_workflow_file()
    registry = WorkflowRegistry()
    registry.register("builder-child-workflow", child_file)
    parent_file = RunsightWorkflowFile.model_validate(_parent_workflow_dict())
    block_def = parent_file.blocks["builder_child_workflow_block"]
    builder = BLOCK_BUILDER_REGISTRY["workflow"]

    block = builder(
        "builder_child_workflow_block",
        block_def,
        {},
        MagicMock(),
        {},
        workflow_registry=registry,
        api_keys={},
        workflow_base_dir=str(tmp_path),
        parent_file_def=parent_file,
    )

    assert isinstance(block, WorkflowBlock)
    assert block.child_workflow.name == "builder_child_workflow"
    assert block.workflow_ref == "builder-child-workflow"
    assert block.max_depth == 7


def test_registered_workflow_builder_requires_workflow_registry_with_actionable_value_error(
    tmp_path: Path,
) -> None:
    """The builder should fail explicitly when workflow_registry is missing."""
    parent_file = RunsightWorkflowFile.model_validate(_parent_workflow_dict())
    block_def = parent_file.blocks["builder_child_workflow_block"]
    builder = BLOCK_BUILDER_REGISTRY["workflow"]

    with pytest.raises(ValueError, match="WorkflowRegistry|workflow_registry|registry"):
        builder(
            "builder_child_workflow_block",
            block_def,
            {},
            MagicMock(),
            {},
            api_keys={},
            workflow_base_dir=str(tmp_path),
            parent_file_def=parent_file,
        )
