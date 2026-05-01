"""
Integration coverage for dispatch delegate routing.

Dispatch block, the delegate tool, and the agentic tool loop are each well
unit-tested in isolation. These integration tests wire them through
parse_workflow_yaml() -> Workflow.run() and verify that:

  Full routing: YAML workflow with a block whose soul uses the
       delegate tool -> runtime routes to the correct exit block -> exit block result
       present in final state.
  Multi-exit routing: Multi-exit dispatch — soul picks port B -> only port B block executes,
       port A block result absent from final state.
  Downstream routing: Dispatch -> selected exit -> downstream block receives the selected
       exit block result through declared inputs.

All tests use mocked LLM (no real API keys). Mocking strategy:
  - LiteLLMClient.achat() is patched via unittest.mock.patch to return controlled
    dicts that simulate tool_call responses and final text answers.
  - No real network calls are ever made.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

_FIXTURE_MODEL = "fixture-dispatch-delegate-model"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    from runsight_core.memory import budget as budget_module

    original_get_model_info = budget_module.get_model_info

    def _get_model_info(model: str):
        if model == _FIXTURE_MODEL:
            return {"max_input_tokens": 8192}
        return original_get_model_info(model)

    monkeypatch.setattr(budget_module, "get_model_info", _get_model_info)


# ---------------------------------------------------------------------------
# Shared response builders (same pattern as test_tool_integration.py)
# ---------------------------------------------------------------------------


def _text_response(
    content: str = "Done.",
    cost_usd: float = 0.001,
    total_tokens: int = 10,
) -> Dict[str, Any]:
    """Build a mock LLM text response (no tool calls)."""
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _tool_call_response(
    tool_name: str,
    arguments: str = "{}",
    call_id: str = "call_001",
    cost_usd: float = 0.002,
    total_tokens: int = 20,
) -> Dict[str, Any]:
    """Build a mock LLM response that contains a single tool call."""
    tc = {
        "id": call_id,
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments},
    }
    return {
        "content": "",
        "cost_usd": cost_usd,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": total_tokens,
        "tool_calls": [tc],
        "finish_reason": "tool_calls",
        "raw_message": {"role": "assistant", "content": "", "tool_calls": [tc]},
    }


# ---------------------------------------------------------------------------
# YAML workflow builders
# ---------------------------------------------------------------------------


_ROUTER_SOUL = {
    "id": "router",
    "kind": "soul",
    "name": "Router Agent",
    "role": "Router Agent",
    "provider": "fixture-provider",
    "model_name": "fixture-dispatch-delegate-model",
    "system_prompt": "You route tasks to the correct exit port using the delegate tool.",
    "tools": ["delegate"],
}

_WORKER_SOUL_A = {
    "id": "worker_a",
    "kind": "soul",
    "name": "Worker A",
    "role": "Worker A",
    "provider": "fixture-provider",
    "model_name": "fixture-dispatch-delegate-model",
    "system_prompt": "You handle port A tasks.",
}

_WORKER_SOUL_B = {
    "id": "worker_b",
    "kind": "soul",
    "name": "Worker B",
    "role": "Worker B",
    "provider": "fixture-provider",
    "model_name": "fixture-dispatch-delegate-model",
    "system_prompt": "You handle port B tasks.",
}

_DOWNSTREAM_SOUL = {
    "id": "downstream",
    "kind": "soul",
    "name": "Downstream Worker",
    "role": "Downstream Worker",
    "provider": "fixture-provider",
    "model_name": "fixture-dispatch-delegate-model",
    "system_prompt": "You process the results from the exit block.",
}


def _two_exit_workflow() -> Dict[str, Any]:
    """Build a YAML dict for a workflow with a router block that has two exits
    (port_a, port_b) and downstream blocks for each exit.

    Flow:
      router (linear, with delegate tool)
        -> port_a: port_a_handler_block (linear)
        -> port_b: port_b_handler_block (linear)
    """
    return {
        "id": "dispatch-delegate-routing-workflow",
        "kind": "workflow",
        "version": "1.0",
        "tools": ["delegate"],
        "souls": {
            "router": _ROUTER_SOUL,
            "worker_a": _WORKER_SOUL_A,
            "worker_b": _WORKER_SOUL_B,
        },
        "blocks": {
            "router": {
                "type": "linear",
                "soul_ref": "router",
                "exits": [
                    {"id": "port_a", "label": "Port A"},
                    {"id": "port_b", "label": "Port B"},
                ],
            },
            "port_a_handler_block": {
                "type": "linear",
                "soul_ref": "worker_a",
            },
            "port_b_handler_block": {
                "type": "linear",
                "soul_ref": "worker_b",
            },
        },
        "workflow": {
            "name": "dispatch_delegate_two_exit",
            "entry": "router",
            "transitions": [
                {"from": "port_a_handler_block", "to": None},
                {"from": "port_b_handler_block", "to": None},
            ],
            "conditional_transitions": [
                {
                    "from": "router",
                    "port_a": "port_a_handler_block",
                    "port_b": "port_b_handler_block",
                },
            ],
        },
    }


def _three_exit_workflow() -> Dict[str, Any]:
    """Build a YAML dict for a workflow where:
      router (linear, delegate tool, 3 exits)
        -> port_a: exit_port_a_handler_block
        -> port_b: exit_port_b_handler_block
        -> port_c: port_c_exit_block

    This verifies multi-exit routing without downstream successor behavior.
    """
    return {
        "id": "dispatch-delegate-routing-workflow",
        "kind": "workflow",
        "version": "1.0",
        "tools": ["delegate"],
        "souls": {
            "router": {
                "id": "router",
                "kind": "soul",
                "name": "Router Agent",
                "role": "Router Agent",
                "provider": "fixture-provider",
                "model_name": "fixture-dispatch-delegate-model",
                "system_prompt": "Route using delegate tool.",
                "tools": ["delegate"],
            },
            "worker_a": _WORKER_SOUL_A,
            "worker_b": _WORKER_SOUL_B,
            "worker_c": {
                "id": "worker_c",
                "kind": "soul",
                "name": "Worker C",
                "role": "Worker C",
                "provider": "fixture-provider",
                "model_name": "fixture-dispatch-delegate-model",
                "system_prompt": "You handle port C tasks.",
            },
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
            "exit_port_a_handler_block": {
                "type": "linear",
                "soul_ref": "worker_a",
            },
            "exit_port_b_handler_block": {
                "type": "linear",
                "soul_ref": "worker_b",
            },
            "port_c_exit_block": {
                "type": "linear",
                "soul_ref": "worker_c",
            },
        },
        "workflow": {
            "name": "dispatch_delegate_three_exit",
            "entry": "router",
            "transitions": [
                {"from": "exit_port_a_handler_block", "to": None},
                {"from": "exit_port_b_handler_block", "to": None},
                {"from": "port_c_exit_block", "to": None},
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


def _three_exit_workflow_with_downstream() -> Dict[str, Any]:
    """Build a three-exit workflow where selected port_b result feeds a successor block."""
    workflow = _three_exit_workflow()
    workflow["souls"]["downstream"] = _DOWNSTREAM_SOUL
    workflow["blocks"]["downstream_linear_block"] = {
        "type": "linear",
        "soul_ref": "downstream",
        "inputs": {"summary": {"from": "exit_port_b_handler_block"}},
    }
    workflow["workflow"]["name"] = "dispatch_delegate_three_exit_downstream"
    workflow["workflow"]["transitions"] = [
        {"from": "exit_port_a_handler_block", "to": None},
        {"from": "exit_port_b_handler_block", "to": "downstream_linear_block"},
        {"from": "port_c_exit_block", "to": None},
        {"from": "downstream_linear_block", "to": None},
    ]
    return workflow


@pytest.mark.asyncio
class TestDispatchDelegateRouting:
    """YAML workflow with a block whose soul calls delegate tool -> runtime
    routes to the correct exit block -> exit block result in final state."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_delegate_to_port_a_routes_to_port_a_handler_block(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Router soul calls delegate(port='port_a') -> port_a_handler_block executes,
        port_a_handler_block result present in final state."""
        workflow = parse_workflow_yaml(_two_exit_workflow(), _base_dir=str(tmp_path))

        # LLM call sequence:
        # 1. Router block: LLM returns delegate tool call for port_a
        # 2. Router block: LLM returns final text after tool result
        # 3. port_a_handler_block: LLM returns text output
        mock_achat.side_effect = [
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_a", "task": "Handle task A"}),
                call_id="del_1",
            ),
            _text_response("Delegated to port A."),
            _text_response("Port A completed the task."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        # Router block must have executed
        assert "router" in final.results, "Router block must produce a result"

        # The exit_handle on the router result must be 'port_a' to trigger routing
        router_result = final.results["router"]
        assert isinstance(router_result, BlockResult)
        assert router_result.exit_handle == "port_a", (
            "Router block result must have exit_handle='port_a' from delegate tool call. "
            f"Got exit_handle={router_result.exit_handle!r}"
        )

        # port_a_handler_block must have executed as the routed target
        assert "port_a_handler_block" in final.results, (
            "port_a_handler_block must execute as the routed exit target for port_a. "
            f"Results contain: {list(final.results.keys())}"
        )
        assert final.results["port_a_handler_block"].output == "Port A completed the task."

        # port_b_handler_block must NOT have executed
        assert "port_b_handler_block" not in final.results, (
            "port_b_handler_block must NOT execute when router delegates to port_a"
        )

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_delegate_to_port_b_routes_to_port_b_handler_block(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Router soul calls delegate(port='port_b') -> port_b_handler_block executes."""
        workflow = parse_workflow_yaml(_two_exit_workflow(), _base_dir=str(tmp_path))

        mock_achat.side_effect = [
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Handle task B"}),
                call_id="del_2",
            ),
            _text_response("Delegated to port B."),
            _text_response("Port B completed the task."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        assert "router" in final.results
        assert final.results["router"].exit_handle == "port_b", (
            "Router result must have exit_handle='port_b'"
        )

        assert "port_b_handler_block" in final.results, (
            "port_b_handler_block must execute when router delegates to port_b. "
            f"Results contain: {list(final.results.keys())}"
        )
        assert "port_a_handler_block" not in final.results, (
            "port_a_handler_block must NOT execute when router delegates to port_b"
        )


# ===========================================================================
# Multi-exit dispatch — soul picks port B, only port B block executes
# ===========================================================================


@pytest.mark.asyncio
class TestMultiExitDispatchRouting:
    """With three exits, soul picks one port -> only that port's block
    executes, other port blocks are absent from final state."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_three_exits_pick_port_b_only_b_executes(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Router with 3 exits picks port_b -> only exit_port_b_handler_block executes."""
        workflow = parse_workflow_yaml(_three_exit_workflow(), _base_dir=str(tmp_path))

        mock_achat.side_effect = [
            # Router: delegate to port_b
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Process via B"}),
                call_id="del_3",
            ),
            _text_response("Routed to port B."),
            # exit_port_b_handler_block executes
            _text_response("Exit block B output."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        # Router executed
        assert "router" in final.results
        assert final.results["router"].exit_handle == "port_b"

        # Only exit_port_b_handler_block executed
        assert "exit_port_b_handler_block" in final.results, (
            f"exit_port_b_handler_block must execute when port_b selected. Results: {list(final.results.keys())}"
        )
        assert "exit_port_a_handler_block" not in final.results, (
            "exit_port_a_handler_block must NOT execute when port_b selected"
        )
        assert "port_c_exit_block" not in final.results, (
            "port_c_exit_block must NOT execute when port_b selected"
        )

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_three_exits_pick_port_c_only_c_executes(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Router with 3 exits picks port_c -> only port_c_exit_block runs."""
        workflow = parse_workflow_yaml(_three_exit_workflow(), _base_dir=str(tmp_path))

        mock_achat.side_effect = [
            # Router: delegate to port_c
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_c", "task": "Process via C"}),
                call_id="del_4",
            ),
            _text_response("Routed to port C."),
            # port_c_exit_block executes
            _text_response("Exit block C output."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        assert "router" in final.results
        assert final.results["router"].exit_handle == "port_c"

        assert "port_c_exit_block" in final.results, (
            f"port_c_exit_block must execute when port_c selected. Results: {list(final.results.keys())}"
        )
        assert "exit_port_a_handler_block" not in final.results
        assert "exit_port_b_handler_block" not in final.results


# ===========================================================================
# Downstream dispatch -> selected exit result reaches successor block
# ===========================================================================


@pytest.mark.asyncio
class TestSelectedDispatchExitFeedsDownstream:
    """Result from dispatch exit block feeds a subsequent linear block
    that executes after the exit."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_selected_exit_result_reaches_downstream_declared_input(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Router -> port_b -> exit_port_b_handler_block -> downstream_linear_block.
        downstream_linear_block must receive the selected exit block result."""
        workflow = parse_workflow_yaml(
            _three_exit_workflow_with_downstream(), _base_dir=str(tmp_path)
        )

        mock_achat.side_effect = [
            # Router: delegate to port_b
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Summarize report"}),
                call_id="del_5",
            ),
            _text_response("Delegated to B."),
            # exit_port_b_handler_block
            _text_response("Report summary from B."),
            # downstream_linear_block (connected after exit_port_b_handler_block)
            _text_response("Final processing of B's output."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        # Full chain executed: router -> exit_port_b_handler_block -> downstream_linear_block
        assert "router" in final.results
        assert "exit_port_b_handler_block" in final.results, (
            f"exit_port_b_handler_block must execute as port_b target. Results: {list(final.results.keys())}"
        )
        assert "downstream_linear_block" in final.results, (
            "downstream_linear_block must execute after exit_port_b_handler_block. "
            f"Results: {list(final.results.keys())}"
        )
        assert final.results["downstream_linear_block"].output == "Final processing of B's output."
        downstream_messages = mock_achat.call_args_list[-1].kwargs["messages"]
        downstream_prompt = downstream_messages[-1]["content"]
        assert "Report summary from B." in downstream_prompt

        # Other exit blocks must not have run
        assert "exit_port_a_handler_block" not in final.results
        assert "port_c_exit_block" not in final.results

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_downstream_linear_block_count_matches_chain_length(
        self, mock_achat: AsyncMock, tmp_path
    ) -> None:
        """Verify that exactly 3 blocks executed: router, exit_port_b_handler_block,
        downstream_linear_block — confirming the chain is correct."""
        workflow = parse_workflow_yaml(
            _three_exit_workflow_with_downstream(), _base_dir=str(tmp_path)
        )

        mock_achat.side_effect = [
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Do B work"}),
                call_id="del_6",
            ),
            _text_response("Routed."),
            _text_response("B result."),
            _text_response("Downstream result."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        executed_blocks = set(final.results.keys())
        expected_blocks = {"router", "exit_port_b_handler_block", "downstream_linear_block"}
        assert expected_blocks <= executed_blocks, (
            f"Expected {expected_blocks} to execute, but got {executed_blocks}"
        )
        # Only the workflow sentinel plus the three expected blocks should be present
        assert executed_blocks - {"workflow"} == expected_blocks, (
            f"Unexpected extra blocks executed: {executed_blocks - expected_blocks - {'workflow'}}"
        )
