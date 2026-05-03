"""Parser tests for delegate tool exit schema contracts."""

from __future__ import annotations

import pytest
from parser_yaml_helpers import tool_validation_soul_workflow_yaml
from runsight_core.yaml.parser import parse_workflow_yaml


def _delegate_soul(workflow, block_id: str = "tool_validation_block"):
    return workflow.blocks[block_id].soul


def _delegate_tool(workflow, block_id: str = "tool_validation_block"):
    soul = _delegate_soul(workflow, block_id)
    assert soul.resolved_tools is not None
    return next(tool for tool in soul.resolved_tools if tool.name == "delegate")


def test_delegate_tool_resolves_with_block_exit_enum() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("delegate",),
            soul_id="gate_agent",
            soul_name="Gate Agent",
            soul_role="Gate Agent",
            soul_prompt="Evaluate and delegate.",
            soul_tools=("delegate",),
            exits=(("approve", "Approve"), ("reject", "Reject")),
        )
    )

    port_schema = _delegate_tool(workflow).parameters["properties"]["port"]
    assert "enum" in port_schema
    assert set(port_schema["enum"]) == {"approve", "reject"}


def test_delegate_tool_exit_enum_contains_all_declared_exits() -> None:
    workflow = parse_workflow_yaml(
        tool_validation_soul_workflow_yaml(
            tool_ids=("delegate",),
            soul_id="router_agent",
            soul_name="Router",
            soul_role="Router",
            soul_prompt="Route to exit.",
            soul_tools=("delegate",),
            exits=(("done", "Done"), ("retry", "Retry"), ("escalate", "Escalate")),
        )
    )

    port_schema = _delegate_tool(workflow).parameters["properties"]["port"]
    assert set(port_schema["enum"]) == {"done", "retry", "escalate"}


def test_delegate_tool_without_block_exits_raises_valueerror() -> None:
    yaml_str = tool_validation_soul_workflow_yaml(
        tool_ids=("delegate",),
        soul_id="gate_agent",
        soul_name="Gate Agent",
        soul_role="Gate Agent",
        soul_prompt="Evaluate and delegate.",
        soul_tools=("delegate",),
    )

    with pytest.raises(ValueError, match="no exits"):
        parse_workflow_yaml(yaml_str)


def test_delegate_without_exits_error_mentions_soul_and_block() -> None:
    yaml_str = tool_validation_soul_workflow_yaml(
        tool_ids=("delegate",),
        soul_id="delegate_evaluator",
        soul_name="Evaluator",
        soul_role="Evaluator",
        soul_prompt="Evaluate.",
        soul_tools=("delegate",),
        block_id="eval_block",
    )

    with pytest.raises(ValueError, match="delegate_evaluator|eval_block"):
        parse_workflow_yaml(yaml_str)


def test_system_delegate_source_is_not_directly_assignable_on_souls() -> None:
    yaml_str = tool_validation_soul_workflow_yaml(
        tool_ids=None,
        soul_id="gate_agent",
        soul_name="Gate Agent",
        soul_role="Gate Agent",
        soul_prompt="Evaluate and delegate.",
        soul_tools=("runsight/delegate",),
        exits=(("approve", "Approve"), ("reject", "Reject")),
    )

    with pytest.raises(ValueError, match="runsight/delegate"):
        parse_workflow_yaml(yaml_str)
