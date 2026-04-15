"""
RUN-629 — E2E: Dispatch — soul calls delegate tool -> exit routing -> downstream block runs.

Dispatch block, the delegate tool, and the agentic tool loop are each well
unit-tested in isolation. These integration tests wire them together end-to-end
through parse_workflow_yaml() -> Workflow.run() and verify that:

  AC1: Full dispatch routing E2E — YAML workflow with a block whose soul uses the
       delegate tool -> runtime routes to the correct exit block -> exit block result
       present in final state.
  AC2: Multi-exit dispatch — soul picks port B -> only port B block executes,
       port A block result absent from final state.
  AC3: Dispatch -> downstream block — result from dispatch exit feeds a subsequent
       linear block that executes after the exit block.

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
    "role": "Router Agent",
    "provider": "openai",
    "model_name": "gpt-4o",
    "system_prompt": "You route tasks to the correct exit port using the delegate tool.",
    "tools": ["delegate"],
}

_WORKER_SOUL_A = {
    "id": "worker_a",
    "role": "Worker A",
    "provider": "openai",
    "model_name": "gpt-4o",
    "system_prompt": "You handle port A tasks.",
}

_WORKER_SOUL_B = {
    "id": "worker_b",
    "role": "Worker B",
    "provider": "openai",
    "model_name": "gpt-4o",
    "system_prompt": "You handle port B tasks.",
}

_DOWNSTREAM_SOUL = {
    "id": "downstream",
    "role": "Downstream Worker",
    "provider": "openai",
    "model_name": "gpt-4o",
    "system_prompt": "You process the results from the exit block.",
}


def _two_exit_workflow() -> Dict[str, Any]:
    """Build a YAML dict for a workflow with a router block that has two exits
    (port_a, port_b) and downstream blocks for each exit.

    Flow:
      router (linear, with delegate tool)
        -> port_a: block_a (linear)
        -> port_b: block_b (linear)
    """
    return {
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
            "block_a": {
                "type": "linear",
                "soul_ref": "worker_a",
            },
            "block_b": {
                "type": "linear",
                "soul_ref": "worker_b",
            },
        },
        "workflow": {
            "name": "dispatch_e2e_two_exit",
            "entry": "router",
            "transitions": [
                {"from": "block_a", "to": None},
                {"from": "block_b", "to": None},
            ],
            "conditional_transitions": [
                {
                    "from": "router",
                    "port_a": "block_a",
                    "port_b": "block_b",
                },
            ],
        },
    }


def _three_exit_workflow_with_downstream() -> Dict[str, Any]:
    """Build a YAML dict for a workflow where:
      router (linear, delegate tool, 3 exits)
        -> port_a: exit_block_a
        -> port_b: exit_block_b
        -> port_c: exit_block_c
      exit_block_b -> downstream_block (linear, sequential after exit)

    This tests AC3: result from dispatch exit feeds a subsequent linear block.
    """
    return {
        "version": "1.0",
        "tools": ["delegate"],
        "souls": {
            "router": {
                "id": "router",
                "role": "Router Agent",
                "provider": "openai",
                "model_name": "gpt-4o",
                "system_prompt": "Route using delegate tool.",
                "tools": ["delegate"],
            },
            "worker_a": _WORKER_SOUL_A,
            "worker_b": _WORKER_SOUL_B,
            "worker_c": {
                "id": "worker_c",
                "role": "Worker C",
                "provider": "openai",
                "model_name": "gpt-4o",
                "system_prompt": "You handle port C tasks.",
            },
            "downstream": _DOWNSTREAM_SOUL,
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
            "exit_block_a": {
                "type": "linear",
                "soul_ref": "worker_a",
            },
            "exit_block_b": {
                "type": "linear",
                "soul_ref": "worker_b",
            },
            "exit_block_c": {
                "type": "linear",
                "soul_ref": "worker_c",
            },
            "downstream_block": {
                "type": "linear",
                "soul_ref": "downstream",
            },
        },
        "workflow": {
            "name": "dispatch_e2e_three_exit_downstream",
            "entry": "router",
            "transitions": [
                {"from": "exit_block_a", "to": None},
                {"from": "exit_block_b", "to": "downstream_block"},
                {"from": "exit_block_c", "to": None},
                {"from": "downstream_block", "to": None},
            ],
            "conditional_transitions": [
                {
                    "from": "router",
                    "port_a": "exit_block_a",
                    "port_b": "exit_block_b",
                    "port_c": "exit_block_c",
                },
            ],
        },
    }


# ===========================================================================
# AC1: Full dispatch routing E2E
# ===========================================================================


@pytest.mark.asyncio
class TestFullDispatchRoutingE2E:
    """YAML workflow with a block whose soul calls delegate tool -> runtime
    routes to the correct exit block -> exit block result in final state."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_delegate_to_port_a_routes_to_block_a(self, mock_achat: AsyncMock) -> None:
        """Router soul calls delegate(port='port_a') -> block_a executes,
        block_a result present in final state."""
        workflow = parse_workflow_yaml(_two_exit_workflow())

        # LLM call sequence:
        # 1. Router block: LLM returns delegate tool call for port_a
        # 2. Router block: LLM returns final text after tool result
        # 3. block_a: LLM returns text output
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

        # block_a must have executed as the routed target
        assert "block_a" in final.results, (
            "block_a must execute as the routed exit target for port_a. "
            f"Results contain: {list(final.results.keys())}"
        )
        assert final.results["block_a"].output == "Port A completed the task."

        # block_b must NOT have executed
        assert "block_b" not in final.results, (
            "block_b must NOT execute when router delegates to port_a"
        )

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_delegate_to_port_b_routes_to_block_b(self, mock_achat: AsyncMock) -> None:
        """Router soul calls delegate(port='port_b') -> block_b executes."""
        workflow = parse_workflow_yaml(_two_exit_workflow())

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

        assert "block_b" in final.results, (
            "block_b must execute when router delegates to port_b. "
            f"Results contain: {list(final.results.keys())}"
        )
        assert "block_a" not in final.results, (
            "block_a must NOT execute when router delegates to port_b"
        )


# ===========================================================================
# AC2: Multi-exit dispatch — soul picks port B, only port B block executes
# ===========================================================================


@pytest.mark.asyncio
class TestMultiExitDispatchRouting:
    """With three exits, soul picks one port -> only that port's block
    executes, other port blocks are absent from final state."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_three_exits_pick_port_b_only_b_executes(self, mock_achat: AsyncMock) -> None:
        """Router with 3 exits picks port_b -> only exit_block_b executes."""
        workflow = parse_workflow_yaml(_three_exit_workflow_with_downstream())

        mock_achat.side_effect = [
            # Router: delegate to port_b
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Process via B"}),
                call_id="del_3",
            ),
            _text_response("Routed to port B."),
            # exit_block_b executes
            _text_response("Exit block B output."),
            # downstream_block executes (connected after exit_block_b)
            _text_response("Downstream processed B's result."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        # Router executed
        assert "router" in final.results
        assert final.results["router"].exit_handle == "port_b"

        # Only exit_block_b executed
        assert "exit_block_b" in final.results, (
            f"exit_block_b must execute when port_b selected. Results: {list(final.results.keys())}"
        )
        assert "exit_block_a" not in final.results, (
            "exit_block_a must NOT execute when port_b selected"
        )
        assert "exit_block_c" not in final.results, (
            "exit_block_c must NOT execute when port_b selected"
        )

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_three_exits_pick_port_c_only_c_executes(self, mock_achat: AsyncMock) -> None:
        """Router with 3 exits picks port_c -> only exit_block_c runs,
        downstream_block does NOT run (it's only connected to exit_block_b)."""
        workflow = parse_workflow_yaml(_three_exit_workflow_with_downstream())

        mock_achat.side_effect = [
            # Router: delegate to port_c
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_c", "task": "Process via C"}),
                call_id="del_4",
            ),
            _text_response("Routed to port C."),
            # exit_block_c executes
            _text_response("Exit block C output."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        assert "router" in final.results
        assert final.results["router"].exit_handle == "port_c"

        assert "exit_block_c" in final.results, (
            f"exit_block_c must execute when port_c selected. Results: {list(final.results.keys())}"
        )
        assert "exit_block_a" not in final.results
        assert "exit_block_b" not in final.results
        # downstream_block is only after exit_block_b, should not run
        assert "downstream_block" not in final.results, (
            "downstream_block must NOT run when port_c is selected "
            "(it is only connected after exit_block_b)"
        )


# ===========================================================================
# AC3: Dispatch -> downstream block — exit result feeds subsequent block
# ===========================================================================


@pytest.mark.asyncio
class TestDispatchExitFeedsDownstream:
    """Result from dispatch exit block feeds a subsequent linear block
    that executes after the exit."""

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_exit_block_result_reaches_downstream(self, mock_achat: AsyncMock) -> None:
        """Router -> port_b -> exit_block_b -> downstream_block.
        downstream_block must execute and its result must be in final state."""
        workflow = parse_workflow_yaml(_three_exit_workflow_with_downstream())

        mock_achat.side_effect = [
            # Router: delegate to port_b
            _tool_call_response(
                "delegate",
                arguments=json.dumps({"port": "port_b", "task": "Summarize report"}),
                call_id="del_5",
            ),
            _text_response("Delegated to B."),
            # exit_block_b
            _text_response("Report summary from B."),
            # downstream_block (connected after exit_block_b)
            _text_response("Final processing of B's output."),
        ]

        state = WorkflowState()

        final = await workflow.run(state)

        # Full chain executed: router -> exit_block_b -> downstream_block
        assert "router" in final.results
        assert "exit_block_b" in final.results, (
            f"exit_block_b must execute as port_b target. Results: {list(final.results.keys())}"
        )
        assert "downstream_block" in final.results, (
            "downstream_block must execute after exit_block_b. "
            f"Results: {list(final.results.keys())}"
        )
        assert final.results["downstream_block"].output == "Final processing of B's output."

        # Other exit blocks must not have run
        assert "exit_block_a" not in final.results
        assert "exit_block_c" not in final.results

    @patch("runsight_core.runner.LiteLLMClient.achat")
    async def test_downstream_block_count_matches_chain_length(self, mock_achat: AsyncMock) -> None:
        """Verify that exactly 3 blocks executed: router, exit_block_b,
        downstream_block — confirming the chain is correct."""
        workflow = parse_workflow_yaml(_three_exit_workflow_with_downstream())

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
        expected_blocks = {"router", "exit_block_b", "downstream_block"}
        assert executed_blocks == expected_blocks, (
            f"Expected exactly {expected_blocks} to execute, but got {executed_blocks}"
        )
