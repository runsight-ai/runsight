"""Smoke coverage for delegate-tool dispatch routing through parsed workflows."""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_FIXTURE_MODEL = "fixture-dispatch-delegate-model"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    from runsight_core import runner as runner_module
    from runsight_core.isolation import handlers as handlers_module
    from runsight_core.memory import budget as budget_module

    original_get_model_info = budget_module.get_model_info
    original_detect_provider = runner_module._detect_provider

    def _get_model_info(model: str):
        if model == _FIXTURE_MODEL:
            return {"max_input_tokens": 8192}
        return original_get_model_info(model)

    def _detect_provider(model: str) -> str:
        if model == _FIXTURE_MODEL:
            return "openai"
        return original_detect_provider(model)

    monkeypatch.setattr(budget_module, "get_model_info", _get_model_info)
    monkeypatch.setattr(runner_module, "_detect_provider", _detect_provider)
    monkeypatch.setattr(handlers_module, "_detect_provider", _detect_provider)


def _text_response(content: str) -> Dict[str, Any]:
    return {
        "content": content,
        "cost_usd": 0.001,
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": 10,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _tool_call_response(port: str) -> Dict[str, Any]:
    tc = {
        "id": "delegate-call",
        "type": "function",
        "function": {
            "name": "delegate",
            "arguments": json.dumps({"port": port, "task": f"Handle {port}"}),
        },
    }
    return {
        "content": "",
        "cost_usd": 0.002,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": 20,
        "tool_calls": [tc],
        "finish_reason": "tool_calls",
        "raw_message": {"role": "assistant", "content": "", "tool_calls": [tc]},
    }


def _three_exit_workflow_with_downstream() -> Dict[str, Any]:
    router_soul = {
        "id": "router",
        "kind": "soul",
        "name": "Router Agent",
        "role": "Router Agent",
        "provider": "fixture-provider",
        "model_name": _FIXTURE_MODEL,
        "system_prompt": "Route tasks to the correct exit port using delegate.",
        "tools": ["delegate"],
    }
    worker_soul = {
        "id": "worker_b",
        "kind": "soul",
        "name": "Worker B",
        "role": "Worker B",
        "provider": "fixture-provider",
        "model_name": _FIXTURE_MODEL,
        "system_prompt": "Handle port B tasks.",
    }
    downstream_soul = {
        "id": "downstream",
        "kind": "soul",
        "name": "Downstream Worker",
        "role": "Downstream Worker",
        "provider": "fixture-provider",
        "model_name": _FIXTURE_MODEL,
        "system_prompt": "Process the selected exit result.",
    }
    return {
        "id": "dispatch-delegate-routing-workflow",
        "kind": "workflow",
        "version": "1.0",
        "tools": ["delegate"],
        "souls": {
            "router": router_soul,
            "worker_a": {**worker_soul, "id": "worker_a", "role": "Worker A"},
            "worker_b": worker_soul,
            "worker_c": {**worker_soul, "id": "worker_c", "role": "Worker C"},
            "downstream": downstream_soul,
        },
        "blocks": {
            "router": {
                "type": "linear",
                "soul_ref": "router",
                "exits": [
                    {"id": "port_a", "label": "Port A"},
                    {"id": "port_b", "label": "Port B"},
                    {"id": "port_c", "label": "Port C"},
                ],
            },
            "exit_port_a_handler_block": {"type": "linear", "soul_ref": "worker_a"},
            "exit_port_b_handler_block": {"type": "linear", "soul_ref": "worker_b"},
            "port_c_exit_block": {"type": "linear", "soul_ref": "worker_c"},
            "downstream_linear_block": {
                "type": "linear",
                "soul_ref": "downstream",
                "inputs": {"summary": {"from": "exit_port_b_handler_block"}},
            },
        },
        "workflow": {
            "name": "dispatch_delegate_three_exit_downstream",
            "entry": "router",
            "transitions": [
                {"from": "exit_port_a_handler_block", "to": None},
                {"from": "exit_port_b_handler_block", "to": "downstream_linear_block"},
                {"from": "port_c_exit_block", "to": None},
                {"from": "downstream_linear_block", "to": None},
            ],
            "conditional_transitions": [
                {
                    "from": "router",
                    "port_a": "exit_port_a_handler_block",
                    "port_b": "exit_port_b_handler_block",
                    "port_c": "port_c_exit_block",
                },
            ],
        },
    }


@pytest.mark.asyncio
@patch("runsight_core.runner.LiteLLMClient.achat")
async def test_delegate_selected_exit_routes_to_downstream_declared_input(
    mock_achat: AsyncMock, tmp_path
) -> None:
    workflow = parse_workflow_yaml(
        _three_exit_workflow_with_downstream(),
        _base_dir=str(tmp_path),
        api_keys={"openai": "dummy-openai-key"},
    )
    mock_achat.side_effect = [
        _tool_call_response("port_b"),
        _text_response("Delegated to B."),
        _text_response("Report summary from B."),
        _text_response("Final processing of B's output."),
    ]

    final = await workflow.run(WorkflowState())

    assert final.results["router"].exit_handle == "port_b"
    assert "exit_port_b_handler_block" in final.results
    assert "downstream_linear_block" in final.results
    assert "exit_port_a_handler_block" not in final.results
    assert "port_c_exit_block" not in final.results
    assert final.results["downstream_linear_block"].output == "Final processing of B's output."

    downstream_prompt = mock_achat.call_args_list[-1].kwargs["messages"][-1]["content"]
    assert "Report summary from B." in downstream_prompt
