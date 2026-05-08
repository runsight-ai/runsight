"""Isolation worker state and context reconstruction contracts."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from isolation_worker_helpers import (
    make_context_envelope,
    run_worker_subprocess,
    worker_ipc_config_env,
)
from runsight_core.isolation.envelope import ResultEnvelope, SoulEnvelope

pytestmark = pytest.mark.real_subprocess_isolation


class TestWorkerFitToBudget:
    """Worker must apply fit_to_budget locally for context windowing."""

    def test_worker_imports_fit_to_budget(self):
        """Worker module uses fit_to_budget from runsight_core.memory.budget."""
        from runsight_core.isolation.worker_support import build_budgeted_history

        # The function should exist and be callable
        assert callable(build_budgeted_history)

    def test_long_history_is_trimmed(self):
        """Conversation history exceeding budget is trimmed before execution."""
        from runsight_core.isolation.worker_support import build_budgeted_history

        # Create a long conversation history
        long_history = [{"role": "user", "content": f"Message {i} " * 500} for i in range(50)]
        trimmed = build_budgeted_history(
            model="gpt-4o",
            system_prompt="You test things.",
            instruction="Say hello",
            conversation_history=long_history,
        )
        # Budget should trim, so the result must be shorter than input.
        assert len(trimmed) < len(long_history)


class TestWorkerStatefulHistory:
    """Worker must return updated conversation_history in ResultEnvelope."""

    def test_result_envelope_contains_conversation_history(self):
        """ResultEnvelope includes conversation_history from execution."""
        envelope = make_context_envelope()
        result = run_worker_subprocess(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert isinstance(result_env.conversation_history, list)

    def test_input_history_is_carried_forward(self):
        """History provided in ContextEnvelope is included in the output."""
        prior_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        envelope = make_context_envelope(conversation_history=prior_history)
        result = run_worker_subprocess(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = ResultEnvelope.model_validate_json(stdout)
        # Output history should contain at least the input messages
        assert len(result_env.conversation_history) >= len(prior_history)


class TestWorkerBlockContextInputs:
    """Worker must preserve resolved Step inputs from ContextEnvelope."""

    @pytest.mark.asyncio
    async def test_envelope_inputs_reach_worker_block_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.block_io import BlockOutput
        from runsight_core.isolation import worker

        envelope = make_context_envelope(inputs={"data": "declared value"})
        captured: dict[str, object] = {}

        class FakeIPCClient:
            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path

            @classmethod
            def from_config(cls, config):
                return cls(socket_path=config.unix_socket.path)

            async def connect(self):
                return {
                    "accepted": True,
                    "error": None,
                }

            async def close(self) -> None:
                return None

        class FakeBlock:
            def __init__(self, block_id: str, soul, runner) -> None:
                self.block_id = block_id
                self.soul = soul
                self.runner = runner
                self.stateful = False

            async def execute(self, ctx):
                captured["inputs"] = dict(ctx.inputs)
                return BlockOutput(output="ok", exit_handle="done")

        def _fake_create_block(envelope_arg, soul_arg, runner_arg):
            return FakeBlock(envelope_arg.block_id, soul_arg, runner_arg)

        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(worker._support, "_create_block", _fake_create_block)

        ipc_config = worker.isolation_ipc.IPCClientConfig.from_env(worker_ipc_config_env())
        result_env, exit_code = await worker._execute_envelope(
            envelope=envelope,
            ipc_config=ipc_config,
        )

        assert exit_code == 0
        assert result_env.error is None
        assert captured["inputs"] == {"data": "declared value"}


class TestWorkerSoulReconstruction:
    """Worker must reconstruct a Soul primitive from SoulEnvelope."""

    def test_reconstruct_soul_from_envelope(self):
        """Worker converts SoulEnvelope to a runsight_core.primitives.Soul."""
        from runsight_core.isolation.worker_support import reconstruct_soul

        soul_env = SoulEnvelope(
            id="worker_soul",
            name="Tester",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        )
        soul = reconstruct_soul(soul_env)
        from runsight_core.primitives import Soul

        assert isinstance(soul, Soul)
        assert soul.id == "worker_soul"
        assert soul.role == "Tester"
        assert soul.system_prompt == "You test things."
        assert soul.model_name == "gpt-4o"
        assert soul.max_tool_iterations == 5

    def test_reconstruct_soul_preserves_extended_runtime_fields(self):
        """Worker soul reconstruction keeps provider/runtime tool-contract fields."""
        from runsight_core.isolation.worker_support import reconstruct_soul

        soul = reconstruct_soul(
            SoulEnvelope(
                id="worker_soul",
                name="Tester",
                role="Tester",
                system_prompt="You test things.",
                model_name="gpt-4o",
                provider="openai",
                temperature=0.0,
                max_tokens=128,
                required_tool_calls=["http_request", "notification_delivery_hook"],
                max_tool_iterations=5,
            )
        )

        assert soul.provider == "openai"
        assert soul.temperature == 0.0
        assert soul.max_tokens == 128
        assert soul.required_tool_calls == ["http_request", "notification_delivery_hook"]

    def test_reconstruct_soul_attaches_resolved_tools(self):
        """Worker should attach IPC-backed resolved_tools to the reconstructed Soul."""
        from runsight_core.isolation.worker_support import reconstruct_soul
        from runsight_core.tools import ToolInstance

        soul_env = SoulEnvelope(
            id="worker_soul",
            name="Tester",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        )
        resolved_tools = [
            ToolInstance(
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                execute=AsyncMock(),
            )
        ]

        soul = reconstruct_soul(soul_env, resolved_tools=resolved_tools)

        assert soul.resolved_tools == resolved_tools


class TestWorkerScopedState:
    """Worker must construct a scoped WorkflowState from envelope data."""

    def test_build_scoped_state(self):
        """Worker builds a WorkflowState from scoped_results and shared_memory."""
        from runsight_core.isolation.worker_support import build_scoped_state

        envelope = make_context_envelope(
            scoped_results={"prev_block": {"output": "hello", "exit_handle": "done"}},
            scoped_shared_memory={"key": "value"},
            conversation_history=[{"role": "user", "content": "hi"}],
        )
        state = build_scoped_state(envelope)
        from runsight_core.state import WorkflowState

        assert isinstance(state, WorkflowState)
        assert "key" in state.shared_memory
        # build_scoped_state constructs state from scoped_results and shared_memory;
        # the instruction is passed separately to the block via the worker harness
        assert "prev_block" in state.results
