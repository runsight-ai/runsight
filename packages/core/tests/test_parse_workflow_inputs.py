from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _workflow_yaml(
    *,
    workflow_id: str = "typed_input_schema_workflow",
    workflow_name: str | None = None,
    inputs: dict[str, dict[str, Any]] | None = None,
    blocks: dict[str, Any] | None = None,
    entry: str = "input_schema_start_step",
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "version": "1.0",
        "id": workflow_id,
        "kind": "workflow",
        "blocks": blocks
        or {
            entry: {
                "type": "code",
                "code": "def main(data):\n    return {'ok': True}",
            }
        },
        "workflow": {
            "id": workflow_id,
            "kind": "workflow",
            "name": workflow_name or workflow_id,
            "entry": entry,
            "transitions": [{"from": entry, "to": None}],
        },
    }
    if inputs is not None:
        raw["inputs"] = inputs
    return raw


def _input_schema_as_dict(input_schema: Any) -> dict[str, dict[str, Any]]:
    assert input_schema is not None
    normalized: dict[str, dict[str, Any]] = {}
    for name, definition in input_schema.items():
        if hasattr(definition, "model_dump"):
            normalized[name] = definition.model_dump()
        else:
            normalized[name] = dict(definition)
    return normalized


def test_parse_workflow_yaml_preserves_explicit_top_level_input_schema() -> None:
    workflow = parse_workflow_yaml(
        _workflow_yaml(
            inputs={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "limit": {
                    "type": "number",
                    "required": False,
                    "default": 3,
                    "description": "Maximum result count",
                },
                "include_sources": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                },
                "filters": {
                    "type": "json",
                    "required": False,
                    "default": {"region": "us"},
                },
                "tags": {
                    "type": "array",
                    "required": False,
                    "default": ["research", "summary"],
                },
                "api_token": {
                    "type": "string",
                    "sensitive": True,
                },
            }
        )
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": "Search query",
            "sensitive": False,
        },
        "limit": {
            "type": "number",
            "required": False,
            "default": 3,
            "description": "Maximum result count",
            "sensitive": False,
        },
        "include_sources": {
            "type": "boolean",
            "required": False,
            "default": True,
            "description": None,
            "sensitive": False,
        },
        "filters": {
            "type": "json",
            "required": False,
            "default": {"region": "us"},
            "description": None,
            "sensitive": False,
        },
        "tags": {
            "type": "array",
            "required": False,
            "default": ["research", "summary"],
            "description": None,
            "sensitive": False,
        },
        "api_token": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": True,
        },
    }


def test_parse_workflow_yaml_without_explicit_inputs_has_no_input_schema() -> None:
    workflow = parse_workflow_yaml(_workflow_yaml())

    assert workflow.input_schema is None


def test_legacy_interface_inputs_are_not_alternate_runtime_schema() -> None:
    legacy_yaml = """
version: "1.0"
id: legacy_interface_workflow
kind: workflow
interface:
  inputs:
    - name: query
      target: shared_memory.query
      type: string
blocks:
  legacy_interface_code_step:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  id: legacy_interface_workflow
  kind: workflow
  name: legacy_interface_workflow
  entry: legacy_interface_code_step
  transitions:
    - from: legacy_interface_code_step
      to: null
"""

    with pytest.raises((ValidationError, ValueError), match="legacy.*interface|unsupported"):
        parse_workflow_yaml(legacy_yaml)

    workflow = parse_workflow_yaml(
        _workflow_yaml(inputs={"query": {"type": "string", "description": "Public input"}})
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": "Public input",
            "sensitive": False,
        }
    }
    assert "target" not in _input_schema_as_dict(workflow.input_schema)["query"]


def test_workflowblock_child_parse_preserves_child_input_schema() -> None:
    child_file = RunsightWorkflowFile.model_validate(
        _workflow_yaml(
            workflow_id="child_input_schema_workflow",
            workflow_name="child_input_schema_workflow",
            inputs={
                "query": {
                    "type": "string",
                    "description": "Child public invocation input",
                },
                "secret_key": {
                    "type": "string",
                    "sensitive": True,
                },
            },
        )
    )
    registry = WorkflowRegistry()
    registry.register("child_input_schema_workflow", child_file)

    parent_workflow = parse_workflow_yaml(
        _workflow_yaml(
            workflow_id="parent_input_schema_workflow",
            workflow_name="parent_input_schema_workflow",
            blocks={
                "child_input_schema_workflow_block": {
                    "type": "workflow",
                    "workflow_ref": "child_input_schema_workflow",
                    "inputs": {
                        "query": "shared_memory.query",
                        "secret_key": "metadata.secret_key",
                    },
                }
            },
            entry="child_input_schema_workflow_block",
        ),
        workflow_registry=registry,
    )

    workflow_block = parent_workflow.blocks["child_input_schema_workflow_block"]
    assert isinstance(workflow_block, WorkflowBlock)
    assert _input_schema_as_dict(workflow_block.child_workflow.input_schema) == {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": "Child public invocation input",
            "sensitive": False,
        },
        "secret_key": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": True,
        },
    }
