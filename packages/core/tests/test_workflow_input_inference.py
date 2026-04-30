from __future__ import annotations

from typing import Any

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml


def _workflow_yaml(
    *,
    workflow_id: str = "workflow-input-inference",
    inputs: dict[str, dict[str, Any]] | None = None,
    blocks: dict[str, Any] | None = None,
    entry: str = "start",
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "version": "1.0",
        "id": workflow_id,
        "kind": "workflow",
        "blocks": blocks
        or {
            "start": _code_block(),
        },
        "workflow": {
            "id": workflow_id,
            "kind": "workflow",
            "name": workflow_id,
            "entry": entry,
            "transitions": [{"from": entry, "to": None}],
        },
    }
    if inputs is not None:
        raw["inputs"] = inputs
    return raw


def _code_block(*, inputs: dict[str, str] | None = None) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "code",
        "code": "def main(data):\n    return {'ok': True}",
    }
    if inputs is not None:
        block["inputs"] = {name: {"from": from_ref} for name, from_ref in inputs.items()}
    return block


def _input_schema_as_dict(input_schema: Any) -> dict[str, dict[str, Any]]:
    assert input_schema is not None
    normalized: dict[str, dict[str, Any]] = {}
    for name, definition in input_schema.items():
        normalized[name] = (
            definition.model_dump() if hasattr(definition, "model_dump") else dict(definition)
        )
    return normalized


def test_parse_workflow_yaml_infers_one_required_string_from_duplicate_leaf_refs() -> None:
    workflow = parse_workflow_yaml(
        _workflow_yaml(
            blocks={
                "start": _code_block(
                    inputs={
                        "query": "workflow.query",
                        "same_query": "workflow.query",
                    }
                )
            }
        )
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": False,
            "source": "inferred",
        }
    }


def test_parse_workflow_yaml_infers_json_from_nested_workflow_ref() -> None:
    workflow = parse_workflow_yaml(
        _workflow_yaml(
            blocks={
                "start": _code_block(
                    inputs={
                        "customer_id": "workflow.payload.customer.id",
                    }
                )
            }
        )
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "payload": {
            "type": "json",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": False,
            "source": "inferred",
        }
    }


def test_inference_only_uses_blocks_with_declared_inputs() -> None:
    workflow = parse_workflow_yaml(
        _workflow_yaml(
            blocks={
                "start": _code_block(inputs={"query": "workflow.query"}),
                "idle": _code_block(),
            },
            entry="start",
        )
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "query": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": False,
            "source": "inferred",
        }
    }
    assert getattr(workflow.blocks["idle"], "declared_inputs") == {}


def test_explicit_schema_wins_and_undeclared_workflow_refs_fail_validation() -> None:
    workflow = parse_workflow_yaml(
        _workflow_yaml(
            inputs={
                "query": {
                    "type": "number",
                    "required": False,
                    "default": 7,
                    "description": "Explicit query override",
                }
            },
            blocks={
                "start": _code_block(inputs={"query": "workflow.query"}),
            },
        )
    )

    assert _input_schema_as_dict(workflow.input_schema) == {
        "query": {
            "type": "number",
            "required": False,
            "default": 7,
            "description": "Explicit query override",
            "sensitive": False,
        }
    }

    with pytest.raises(ValueError, match="workflow\\.query|undeclared"):
        parse_workflow_yaml(
            _workflow_yaml(
                inputs={"topic": {"type": "string"}},
                blocks={
                    "start": _code_block(inputs={"query": "workflow.query"}),
                },
            )
        )


def test_bare_workflow_ref_is_invalid() -> None:
    with pytest.raises(ValueError, match="workflow.*input|workflow.*ref"):
        parse_workflow_yaml(
            _workflow_yaml(
                blocks={
                    "start": _code_block(inputs={"bad": "workflow"}),
                }
            )
        )
