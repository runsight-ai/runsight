"""
Failing tests for RUN-399: ISO-004 — Worker entry point (subprocess main loop).

Tests cover every AC item:
1.  LiteLLMClient direct LLM calls
2.  IPCClient for tools only
3.  Heartbeat with phase on stderr
4.  Errors in ResultEnvelope
5.  fit_to_budget local
6.  Stateful history round-trips
7.  Zero workflow/observer/api imports
8.  Missing RUNSIGHT_GRANT_TOKEN env var: exit 1 with clear error
9.  Missing RUNSIGHT_IPC_SOCKET env var: exit 1 with clear error
10. Exit 0/1
"""

from __future__ import annotations

import inspect
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    HeartbeatMessage,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
    ToolDefEnvelope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context_envelope(**overrides) -> ContextEnvelope:
    """Build a minimal valid ContextEnvelope for test purposes."""
    defaults = dict(
        block_id="blk_1",
        block_type="linear",
        block_config={},
        soul=SoulEnvelope(
            id="soul_1",
            name="Tester",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        ),
        tools=[],
        prompt=PromptEnvelope(
            id="task_1",
            instruction="Say hello",
            context={},
        ),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )
    defaults.update(overrides)
    return ContextEnvelope(**defaults)


def _run_worker(
    envelope: ContextEnvelope,
    env_extra: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess:
    """Invoke the worker as a subprocess, piping the envelope via stdin."""
    env = os.environ.copy()
    # Defaults for required env vars
    env.setdefault("RUNSIGHT_GRANT_TOKEN", "grant-token-123")
    env.setdefault("RUNSIGHT_IPC_SOCKET", "/tmp/test_ipc.sock")
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        [sys.executable, "-m", "runsight_core.isolation.worker"],
        input=envelope.model_dump_json(),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# ==============================================================================
# RUN-395: ProxiedLLMClient for subprocess-side LLM calls over IPC
# ==============================================================================


class TestRUN395ProxiedLLMClientContract:
    """Worker LLM path must use ProxiedLLMClient over IPC, not direct LiteLLM calls."""

    def test_worker_module_exposes_proxied_llm_client_symbol(self):
        from runsight_core.isolation import worker_proxies

        ProxiedLLMClient = getattr(worker_proxies, "ProxiedLLMClient", None)
        assert ProxiedLLMClient is not None

    def test_proxied_achat_signature_matches_litellm_shape(self):
        from runsight_core.isolation import worker_proxies

        ProxiedLLMClient = getattr(worker_proxies, "ProxiedLLMClient", None)
        assert ProxiedLLMClient is not None

        params = inspect.signature(ProxiedLLMClient.achat).parameters
        assert "messages" in params
        assert "system_prompt" in params
        assert "temperature" in params
        assert "tools" in params
        assert "tool_choice" in params
        assert any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())

    @pytest.mark.asyncio
    async def test_proxied_achat_routes_llm_call_over_ipc_stream(self):
        from runsight_core.isolation import worker_proxies

        ProxiedLLMClient = getattr(worker_proxies, "ProxiedLLMClient", None)
        assert ProxiedLLMClient is not None

        messages = [{"role": "user", "content": "hello"}]
        tools = [
            {"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}
        ]
        calls: list[tuple[str, dict[str, object]]] = []

        class FakeIPCClient:
            async def request_stream(self, action: str, payload: dict[str, object]):
                calls.append((action, payload))
                yield {
                    "content": "hi",
                    "cost_usd": 0.12,
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                    "total_tokens": 5,
                    "tool_calls": [],
                    "finish_reason": "stop",
                }

        proxied = ProxiedLLMClient(model_name="gpt-4o", ipc_client=FakeIPCClient())
        response = await proxied.achat(
            messages=messages,
            system_prompt="be concise",
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

        assert calls and calls[0][0] == "llm_call"
        payload = calls[0][1]
        assert payload["model"] == "gpt-4o"
        assert payload["messages"] == messages
        assert payload["tools"] == tools
        assert payload["tool_choice"] == "auto"
        assert payload["temperature"] == 0.2
        assert response == {
            "content": "hi",
            "cost_usd": 0.12,
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    @pytest.mark.asyncio
    async def test_proxied_achat_forwards_extra_kwargs_into_llm_call_payload(self):
        from runsight_core.isolation import worker_proxies

        ProxiedLLMClient = getattr(worker_proxies, "ProxiedLLMClient", None)
        assert ProxiedLLMClient is not None

        captured_payload: dict[str, object] = {}

        class FakeIPCClient:
            async def request_stream(self, action: str, payload: dict[str, object]):
                nonlocal captured_payload
                assert action == "llm_call"
                captured_payload = payload
                yield {
                    "content": "ok",
                    "cost_usd": 0.0,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                    "tool_calls": [],
                    "finish_reason": "stop",
                }

        proxied = ProxiedLLMClient(model_name="gpt-4o", ipc_client=FakeIPCClient())
        await proxied.achat(
            messages=[{"role": "user", "content": "hello"}],
            system_prompt="sys",
            max_tokens=512,
            response_format={"type": "json_object"},
            seed=7,
        )

        assert captured_payload["max_tokens"] == 512
        assert captured_payload["response_format"] == {"type": "json_object"}
        assert captured_payload["seed"] == 7

    @pytest.mark.asyncio
    async def test_proxied_achat_raises_when_ipc_returns_error(self):
        from runsight_core.isolation import worker_proxies

        ProxiedLLMClient = getattr(worker_proxies, "ProxiedLLMClient", None)
        assert ProxiedLLMClient is not None

        class FakeIPCClient:
            async def request_stream(self, action: str, payload: dict[str, object]):
                raise ConnectionError("upstream llm_call failed")
                yield {}

        proxied = ProxiedLLMClient(model_name="gpt-4o", ipc_client=FakeIPCClient())
        with pytest.raises((RuntimeError, ConnectionError, ValueError)):
            await proxied.achat(messages=[{"role": "user", "content": "hello"}])

    def test_worker_runner_model_override_uses_proxied_client_not_direct_litellm(self):
        from runsight_core.isolation.worker_proxies import ProxiedLLMClient, create_runner
        from runsight_core.primitives import Soul

        shared_ipc_client = object()
        runner = create_runner(model_name="gpt-4o", ipc_client=shared_ipc_client)
        alt_soul = Soul(
            id="soul-alt",
            kind="soul",
            name="Alt",
            role="Alt",
            system_prompt="alt",
            model_name="gpt-4.1-mini",
            provider="openai",
        )
        client = runner._get_client(alt_soul)
        assert isinstance(client, ProxiedLLMClient)
        assert client._ipc_client is shared_ipc_client

    def test_default_worker_runner_path_does_not_construct_direct_litellm_clients(self):
        from runsight_core.isolation.worker_proxies import ProxiedLLMClient, create_runner

        with patch(
            "runsight_core.runner.LiteLLMClient",
            side_effect=AssertionError("direct LiteLLMClient construction is forbidden in worker"),
        ):
            runner = create_runner(model_name="gpt-4o", ipc_client=object())
            assert isinstance(runner.llm_client, ProxiedLLMClient)

    @pytest.mark.asyncio
    async def test_worker_runner_failover_path_uses_proxied_client_for_fallback(self):
        from runsight_core.isolation.worker_proxies import ProxiedLLMClient, create_runner
        from runsight_core.primitives import Soul
        from runsight_core.runner import FallbackRoute

        runner = create_runner(model_name="gpt-4o", ipc_client=object())
        runner.fallback_routes = {
            "openai": FallbackRoute(
                source_provider_id="openai",
                target_provider_id="anthropic",
                target_model_name="claude-3-opus-20240229",
            )
        }

        call_models: list[str] = []

        class FailThenSucceedClient(ProxiedLLMClient):
            async def achat(
                self,
                messages,
                system_prompt=None,
                temperature=None,
                tools=None,
                tool_choice=None,
                **kwargs,
            ):  # type: ignore[override]
                call_models.append(self.model_name)
                if self.model_name == "gpt-4o":
                    raise ConnectionError("retryable provider failure")
                return {
                    "content": "fallback-ok",
                    "cost_usd": 0.01,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                    "tool_calls": [],
                    "finish_reason": "stop",
                    "raw_message": {"role": "assistant", "content": "fallback-ok"},
                }

        runner._get_client = lambda soul: FailThenSucceedClient(  # type: ignore[method-assign]
            model_name=soul.model_name or "gpt-4o",
            ipc_client=object(),
        )

        primary_soul = Soul(
            id="soul-primary",
            kind="soul",
            name="Primary",
            role="Primary",
            system_prompt="primary",
            model_name="gpt-4o",
            provider="openai",
        )
        response, used_soul, allow_failover = await runner._achat_with_failover(
            primary_soul,
            messages=[{"role": "user", "content": "hello"}],
            system_prompt=primary_soul.system_prompt,
        )

        assert response["content"] == "fallback-ok"
        assert used_soul.model_name == "claude-3-opus-20240229"
        assert allow_failover is False
        assert call_models == ["gpt-4o", "claude-3-opus-20240229"]

    def test_reconstruct_soul_preserves_extended_runtime_fields(self):
        """Worker soul reconstruction keeps provider/runtime tool-contract fields."""
        from runsight_core.isolation.worker_support import reconstruct_soul

        soul = reconstruct_soul(
            SoulEnvelope(
                id="soul_1",
                name="Tester",
                role="Tester",
                system_prompt="You test things.",
                model_name="gpt-4o",
                provider="openai",
                temperature=0.0,
                max_tokens=128,
                required_tool_calls=["http_request", "slack_webhook"],
                max_tool_iterations=5,
            )
        )

        assert soul.provider == "openai"
        assert soul.temperature == 0.0
        assert soul.max_tokens == 128
        assert soul.required_tool_calls == ["http_request", "slack_webhook"]


# ==============================================================================
# AC2: IPCClient for tools only — tools are IPC stubs, not real implementations
# ==============================================================================


class TestWorkerIPCToolStubs:
    """Tools must be routed through IPCClient, not executed locally."""

    def test_worker_creates_tool_stubs_from_envelope(self):
        """Worker converts ToolDefEnvelope list into IPC-backed tool stubs."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs
        from runsight_core.tools import ToolInstance

        tool_defs = [
            ToolDefEnvelope(
                source="http",
                config={"url": "https://example.com"},
                exits=["done"],
                name="http_lookup",
                description="Look up a URL",
                parameters={"type": "object", "properties": {"url": {"type": "string"}}},
                tool_type="http",
            ),
        ]
        stubs = create_tool_stubs(tool_defs, ipc_client=object())
        assert len(stubs) == 1
        assert isinstance(stubs[0], ToolInstance)

    def test_tool_stubs_are_callable(self):
        """Each tool stub must be callable (used as a tool function)."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="http",
                config={"url": "https://example.com"},
                exits=["done"],
                name="http_lookup",
                description="Look up a URL",
                parameters={"type": "object", "properties": {"url": {"type": "string"}}},
                tool_type="http",
            ),
        ]
        stubs = create_tool_stubs(tool_defs, ipc_client=object())
        assert callable(stubs[0].execute)

    def test_tool_stub_openai_schema_comes_from_envelope_metadata(self):
        """Stub to_openai_schema should use name/description/parameters from ToolDefEnvelope."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="custom/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        stub = create_tool_stubs(tool_defs, ipc_client=object())[0]
        schema = stub.to_openai_schema()

        assert schema == {
            "type": "function",
            "function": {
                "name": "echo_tool",
                "description": "Echoes a string",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
            },
        }

    @pytest.mark.asyncio
    async def test_tool_stub_execute_sends_tool_call_request_to_ipc_client(self):
        """Stub execute() should call IPCClient.request('tool_call', ...) with tool name + args."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="custom/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        client = MagicMock()
        client.request = AsyncMock(return_value={"output": "echo:hi"})

        stub = create_tool_stubs(tool_defs, ipc_client=client)[0]
        result = await stub.execute({"value": "hi"})

        client.request.assert_awaited_once_with(
            "tool_call",
            {"name": "echo_tool", "arguments": {"value": "hi"}},
        )
        assert result == "echo:hi"

    @pytest.mark.asyncio
    async def test_tool_stub_returns_error_string_on_ipc_error(self):
        """IPC error payloads should come back as 'Error: ...' strings."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="custom/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        client = MagicMock()
        client.request = AsyncMock(return_value={"error": "tool failed"})

        stub = create_tool_stubs(tool_defs, ipc_client=client)[0]
        result = await stub.execute({"value": "hi"})

        assert result == "Error: tool failed"


# ==============================================================================
# AC3: Heartbeat with phase on stderr
# ==============================================================================


class TestWorkerHeartbeat:
    """Worker must emit heartbeat JSON lines on stderr with phase info."""

    def test_heartbeat_emitted_on_stderr(self):
        """Running the worker produces heartbeat lines on stderr."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
        # At least one heartbeat should appear
        heartbeats = []
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    heartbeats.append(data)
            except json.JSONDecodeError:
                continue
        assert len(heartbeats) >= 1, (
            f"Expected at least 1 heartbeat on stderr, got: {result.stderr}"
        )

    def test_heartbeat_contains_phase(self):
        """Each heartbeat must include a 'phase' field."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = result.stderr.strip().splitlines()
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    assert "phase" in data, f"Heartbeat missing 'phase': {data}"
                    assert isinstance(data["phase"], str)
                    break
            except json.JSONDecodeError:
                continue
        else:
            pytest.fail(f"No heartbeat found on stderr: {result.stderr}")

    def test_heartbeat_validates_as_heartbeat_message(self):
        """Each heartbeat line on stderr must validate as HeartbeatMessage."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
        stderr_lines = result.stderr.strip().splitlines()
        found = False
        for line in stderr_lines:
            try:
                data = json.loads(line)
                if "heartbeat" in data:
                    hb = HeartbeatMessage.model_validate(data)
                    assert hb.phase is not None
                    found = True
                    break
            except json.JSONDecodeError:
                continue
        assert found, f"No valid HeartbeatMessage on stderr: {result.stderr}"


# ==============================================================================
# AC4: Errors in ResultEnvelope
# ==============================================================================


class TestWorkerErrorsInResultEnvelope:
    """Errors must be captured in ResultEnvelope with error + error_type."""

    def test_error_produces_result_envelope_on_stdout(self):
        """When execution fails, stdout still contains a valid ResultEnvelope."""
        # Use an invalid block_type to trigger an error
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert result_env.error_type is not None

    def test_error_result_has_block_id(self):
        """Error ResultEnvelope preserves the block_id from the context."""
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        result_env = ResultEnvelope.model_validate_json(result.stdout.strip())
        assert result_env.block_id == "blk_1"


# ==============================================================================
# AC5: fit_to_budget local
# ==============================================================================


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
        # Budget should trim — result must be shorter than input
        assert len(trimmed) < len(long_history)


# ==============================================================================
# AC6: Stateful history round-trips
# ==============================================================================


class TestWorkerStatefulHistory:
    """Worker must return updated conversation_history in ResultEnvelope."""

    def test_result_envelope_contains_conversation_history(self):
        """ResultEnvelope includes conversation_history from execution."""
        envelope = _make_context_envelope()
        result = _run_worker(envelope)
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
        envelope = _make_context_envelope(conversation_history=prior_history)
        result = _run_worker(envelope)
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

        envelope = _make_context_envelope(inputs={"data": "declared value"})
        captured: dict[str, object] = {}

        class FakeIPCClient:
            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path

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

        result_env, exit_code = await worker._execute_envelope(
            envelope=envelope,
            ipc_socket="/tmp/rs-inputs.sock",
        )

        assert exit_code == 0
        assert result_env.error is None
        assert captured["inputs"] == {"data": "declared value"}


# ==============================================================================
# AC7: Zero workflow/observer/api imports
# ==============================================================================


class TestWorkerImportBoundary:
    """Worker must NOT import runsight_core.workflow, observer, or api modules."""

    def test_no_workflow_import(self):
        """Worker source must not import runsight_core.workflow."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.workflow" not in source, (
            "Worker must not import runsight_core.workflow"
        )

    def test_no_observer_import(self):
        """Worker source must not import runsight_core.observer."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.observer" not in source, (
            "Worker must not import runsight_core.observer"
        )

    def test_no_api_import(self):
        """Worker source must not import runsight_api."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_api" not in source, "Worker must not import runsight_api"

    def test_no_sqlmodel_import(self):
        """Worker source must not import sqlmodel."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "sqlmodel" not in source, "Worker must not import sqlmodel"


# ==============================================================================
# AC8: Missing RUNSIGHT_GRANT_TOKEN → exit 1 with clear error
# ==============================================================================


class TestWorkerMissingGrantToken:
    """Missing RUNSIGHT_GRANT_TOKEN must exit 1 with error in ResultEnvelope."""

    def test_missing_grant_token_exits_nonzero(self):
        """Worker exits with code 1 when RUNSIGHT_GRANT_TOKEN is absent."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_GRANT_TOKEN", None)
        env_override["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope, not just a Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing API key"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_missing_grant_token_has_error_in_result(self):
        """ResultEnvelope on stdout describes the missing grant token."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_GRANT_TOKEN", None)
        env_override["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on env error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_GRANT_TOKEN" in result_env.error


class TestRUN398WorkerGrantTokenContract:
    """RUN-398: worker authenticates via grant token, not raw API key env injection."""

    def test_worker_source_does_not_reference_block_api_key_env_var(self):
        """Security contract: worker must not read RUNSIGHT_BLOCK_API_KEY at all."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "RUNSIGHT_BLOCK_API_KEY" not in source

    def test_worker_does_not_fail_for_missing_block_api_key_when_grant_token_present(self):
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_BLOCK_API_KEY", None)
        env_override["RUNSIGHT_GRANT_TOKEN"] = "grant-token-123"
        env_override["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"

        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )

        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_BLOCK_API_KEY" not in result_env.error


class TestRUN396WorkerCapabilityNegotiationStartup:
    """RUN-396: worker startup uses IPCClient.connect capability handshake."""

    @pytest.mark.asyncio
    async def test_tool_stub_uses_connect_handshake_without_legacy_capability_request(self):
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="custom/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        call_log: list[tuple[str, str | None]] = []

        class FakeIPCClient:
            def __init__(self, *, socket_path: str) -> None:
                self._socket_path = socket_path

            async def connect(self):
                call_log.append(("connect", None))
                return {
                    "id": "cap-1",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["tool_call"],
                    "engine_context": {
                        "budget_remaining_usd": 15.0,
                        "trace_id": "trace-worker-396",
                        "run_id": "run-worker-396",
                        "block_id": "blk_1",
                    },
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                call_log.append(("request", action))
                if action == "tool_call":
                    return {"output": f"echo:{payload['arguments']['value']}"}
                return {"error": "unexpected action"}

        ipc_client = FakeIPCClient(socket_path="/tmp/test.sock")
        await ipc_client.connect()
        stub = create_tool_stubs(tool_defs, ipc_client=ipc_client)[0]
        result = await stub.execute({"value": "hello"})

        assert call_log[0] == ("connect", None)
        assert ("request", "capability_negotiation") not in call_log
        assert ("request", "tool_call") in call_log
        assert result == "echo:hello"


class TestRUN399WorkerRedesignContract:
    """RUN-399: single shared IPC client + expanded block type creation."""

    @pytest.mark.asyncio
    async def test_create_tool_stubs_uses_shared_authenticated_ipc_client(self):
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="custom/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        class SharedIPCClient:
            def __init__(self) -> None:
                self.connect_calls = 0
                self.request_calls: list[tuple[str, dict[str, object]]] = []

            async def connect(self):
                self.connect_calls += 1
                return {"accepted": True, "error": None}

            async def request(self, action: str, payload: dict[str, object]):
                self.request_calls.append((action, payload))
                return {"output": f"echo:{payload['arguments']['value']}"}

        shared_client = SharedIPCClient()
        stubs = create_tool_stubs(tool_defs, ipc_client=shared_client)
        result = await stubs[0].execute({"value": "hello"})

        assert shared_client.connect_calls == 0
        assert shared_client.request_calls == [
            (
                "tool_call",
                {"name": "echo_tool", "arguments": {"value": "hello"}},
            )
        ]
        assert result == "echo:hello"

    def test_create_runner_reuses_shared_ipc_client_for_default_and_alt_models(self):
        from runsight_core.isolation.worker_proxies import create_runner
        from runsight_core.primitives import Soul

        shared_client = object()
        runner = create_runner(model_name="gpt-4o", ipc_client=shared_client)

        default_client = runner.llm_client
        alt_soul = Soul(
            id="alt",
            kind="soul",
            name="Alt",
            role="Alt",
            system_prompt="alt",
            model_name="gpt-4.1-mini",
            provider="openai",
        )
        alt_client = runner._get_client(alt_soul)

        assert default_client._ipc_client is shared_client
        assert alt_client._ipc_client is shared_client

    def test_main_uses_single_ipc_client_and_connects_once_before_llm_and_tool_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import worker
        from runsight_core.tools import ToolInstance

        envelope = _make_context_envelope(
            tools=[
                ToolDefEnvelope(
                    source="custom/echo",
                    config={},
                    exits=["done"],
                    name="echo_tool",
                    description="Echoes a string",
                    parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                    tool_type="custom",
                )
            ]
        )

        class FakeIPCClient:
            instances: list["FakeIPCClient"] = []

            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path
                self.connect_calls = 0
                self.tool_calls: list[dict[str, object]] = []
                self.llm_calls: list[dict[str, object]] = []
                FakeIPCClient.instances.append(self)

            async def connect(self):
                self.connect_calls += 1
                return {
                    "id": "cap-399",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["llm_call", "tool_call"],
                    "engine_context": {},
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                if action == "tool_call":
                    self.tool_calls.append(payload)
                    return {"output": "tool-ok"}
                return {"error": "unexpected"}

            async def request_stream(self, action: str, payload: dict[str, object]):
                if action == "llm_call":
                    self.llm_calls.append(payload)
                    yield {
                        "content": "ok",
                        "cost_usd": 0.01,
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }
                    return
                raise RuntimeError("unexpected action")

        def _create_tool_stubs_with_shared_ipc_client(
            tool_envelopes: list[ToolDefEnvelope],
            *,
            ipc_client,
        ):
            stubs: list[ToolInstance] = []
            for tool_def in tool_envelopes:

                async def _execute(args: dict[str, object], td: ToolDefEnvelope = tool_def) -> str:
                    result = await ipc_client.request(
                        "tool_call",
                        {"name": td.name, "arguments": args},
                    )
                    return str(result.get("output", ""))

                stubs.append(
                    ToolInstance(
                        name=tool_def.name,
                        description=tool_def.description,
                        parameters=tool_def.parameters,
                        execute=_execute,
                    )
                )
            return stubs

        def _create_runner_with_shared_ipc_client(model_name: str, *, ipc_client):
            return worker._proxies.ProxiedRunsightTeamRunner(
                model_name=model_name, ipc_client=ipc_client
            )

        class _FakeBlock:
            def __init__(self, block_id_arg: str, soul_arg, runner_arg) -> None:
                self.block_id = block_id_arg
                self._soul = soul_arg
                self._runner = runner_arg

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                await self._soul.resolved_tools[0].execute({"value": "hello"})
                await self._runner.llm_client.achat(messages=[{"role": "user", "content": "ping"}])
                return BlockOutput(output="ok", exit_handle="done", cost_usd=0.01, total_tokens=2)

        def _fake_create_block(envelope_arg, soul_arg, runner_arg):
            return _FakeBlock(envelope_arg.block_id, soul_arg, runner_arg)

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-399")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", "/tmp/rs-run399.sock")
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *args, **kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda interval=5.0: None)
        monkeypatch.setattr(worker, "_heartbeat_stop", threading.Event())
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(
            worker._proxies, "create_tool_stubs", _create_tool_stubs_with_shared_ipc_client
        )
        monkeypatch.setattr(worker._proxies, "create_runner", _create_runner_with_shared_ipc_client)
        monkeypatch.setattr(worker._support, "_create_block", _fake_create_block)
        monkeypatch.setattr(sys, "stdin", io.StringIO(envelope.model_dump_json()))
        captured_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured_stdout)

        with pytest.raises(SystemExit) as exc_info:
            worker.main()

        result_env = ResultEnvelope.model_validate_json(captured_stdout.getvalue().strip())

        assert exc_info.value.code == 0
        assert result_env.error is None
        assert len(FakeIPCClient.instances) == 1
        assert FakeIPCClient.instances[0].connect_calls == 1
        assert FakeIPCClient.instances[0].tool_calls
        assert FakeIPCClient.instances[0].llm_calls

    @pytest.mark.parametrize("block_type", ["GateBlock", "gate"])
    def test_create_block_supports_gate_aliases_with_gate_soul_fields(self, block_type: str):
        from runsight_core.blocks.gate import GateBlock
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = _make_context_envelope(
            block_type=block_type,
            block_config={
                "eval_key": "result_a",
                "extract_field": "summary",
                "gate_soul": {
                    "id": "gate_soul_1",
                    "role": "Gate Reviewer",
                    "system_prompt": "Evaluate result quality",
                    "model_name": "gpt-4o-mini",
                },
            },
        )
        fallback_soul = reconstruct_soul(envelope.soul)
        block = _create_block(envelope, fallback_soul, runner=object())

        assert isinstance(block, GateBlock)
        assert block.eval_key == "result_a"
        assert block.extract_field == "summary"
        assert block.gate_soul.id == "gate_soul_1"

    @pytest.mark.parametrize("block_type", ["SynthesizeBlock", "synthesize"])
    def test_create_block_supports_synthesize_aliases_with_synthesizer_soul(
        self,
        block_type: str,
    ):
        from runsight_core.blocks.synthesize import SynthesizeBlock
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = _make_context_envelope(
            block_type=block_type,
            block_config={
                "input_block_ids": ["a", "b"],
                "synthesizer_soul": {
                    "id": "synth_soul_1",
                    "role": "Synthesis Agent",
                    "system_prompt": "Merge findings",
                    "model_name": "gpt-4.1-mini",
                },
            },
        )
        fallback_soul = reconstruct_soul(envelope.soul)
        block = _create_block(envelope, fallback_soul, runner=object())

        assert isinstance(block, SynthesizeBlock)
        assert block.input_block_ids == ["a", "b"]
        assert block.synthesizer_soul.id == "synth_soul_1"

    @pytest.mark.parametrize("block_type", ["DispatchBlock", "dispatch"])
    def test_create_block_supports_dispatch_aliases(self, block_type: str):
        from runsight_core.blocks.dispatch import DispatchBlock
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = _make_context_envelope(
            block_type=block_type,
            block_config={
                "branches": [
                    {
                        "exit_id": "branch_a",
                        "label": "Branch A",
                        "task_instruction": "Do A",
                        "soul": {
                            "id": "dispatch_soul_1",
                            "role": "Dispatch Agent",
                            "system_prompt": "Handle branch A",
                            "model_name": "gpt-4o-mini",
                        },
                    }
                ]
            },
        )
        fallback_soul = reconstruct_soul(envelope.soul)
        block = _create_block(envelope, fallback_soul, runner=object())

        assert isinstance(block, DispatchBlock)
        assert len(block.branches) == 1
        assert block.branches[0].exit_id == "branch_a"
        assert block.branches[0].soul.id == "dispatch_soul_1"


class TestRUN812WorkerAssertionBlockContract:
    """RUN-812: worker must construct assertion adapters for assertion block envelopes."""

    def test_create_block_supports_assertion_block_type_and_returns_executable_adapter(self):
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = _make_context_envelope(
            block_id="assertion_1",
            block_type="assertion",
            block_config={
                "assertion": {
                    "type": "llm_judge",
                    "config": {"rubric": "Score factual quality"},
                },
                "output_to_grade": "Candidate response to grade",
                "judge_soul": {
                    "id": "judge_soul_1",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
            scoped_results={
                "target_block": {
                    "output": "Candidate response to grade",
                    "exit_handle": "done",
                }
            },
        )

        fallback_soul = reconstruct_soul(envelope.soul)
        block = _create_block(envelope, fallback_soul, runner=object())

        assert callable(getattr(block, "execute", None))

    @pytest.mark.asyncio
    async def test_assertion_block_execution_serializes_grading_result_json(self):
        from runsight_core.assertions.base import GradingResult
        from runsight_core.assertions.scoring import AssertionsResult
        from runsight_core.isolation import worker

        async def fake_run_assertions(*args, **kwargs) -> AssertionsResult:
            agg = AssertionsResult()
            agg.add_result(
                GradingResult(
                    passed=True,
                    score=0.85,
                    reason="judge accepted output",
                    named_scores={"coherence": 0.85},
                    assertion_type="llm_judge",
                    metadata={"judge_model": "gpt-4o-mini"},
                )
            )
            return agg

        with patch("runsight_core.assertions.registry.run_assertions", fake_run_assertions):
            envelope = _make_context_envelope(
                block_id="assertion_serialize",
                block_type="assertion",
                block_config={
                    "assertion": {
                        "type": "llm_judge",
                        "config": {"rubric": "Score factual quality"},
                    },
                    "output_to_grade": "Candidate response to grade",
                    "judge_soul": {
                        "id": "judge_soul_1",
                        "role": "LLM Judge",
                        "system_prompt": "Grade this answer against the rubric.",
                        "model_name": "gpt-4o-mini",
                    },
                },
                scoped_results={
                    "target_block": {
                        "output": "Candidate response to grade",
                        "exit_handle": "done",
                    }
                },
            )
            soul = worker._support.reconstruct_soul(envelope.soul)
            runner = worker._proxies.create_runner(
                model_name=envelope.soul.model_name, ipc_client=object()
            )
            block = worker._support._create_block(envelope, soul, runner=runner)
            state = worker._support.build_scoped_state(envelope)
            from runsight_core.block_io import BlockContext

            ctx = BlockContext(
                block_id=envelope.block_id,
                instruction=envelope.prompt.instruction,
                context=None,
                inputs={},
                conversation_history=[],
                soul=soul,
                model_name=envelope.soul.model_name,
                state_snapshot=state,
            )
            block_output = await block.execute(ctx)

        serialized = block_output.output
        assert isinstance(serialized, str)
        payload = json.loads(serialized)
        assert payload["passed"] is True
        assert payload["score"] == pytest.approx(0.85)
        assert payload["reason"] == "judge accepted output"
        assert payload["named_scores"]["coherence"] == pytest.approx(0.85)
        assert payload["metadata"]["judge_model"] == "gpt-4o-mini"

    def test_assertion_main_rejects_execution_when_capability_handshake_not_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import worker

        envelope = _make_context_envelope(
            block_id="assertion_auth_fail",
            block_type="assertion",
            block_config={
                "assertion": {"type": "llm_judge", "config": {"rubric": "strict"}},
                "output_to_grade": "Candidate response",
                "judge_soul": {
                    "id": "judge_soul_1",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
        )

        class FakeIPCClient:
            instances: list["FakeIPCClient"] = []

            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path
                self.connect_calls = 0
                FakeIPCClient.instances.append(self)

            async def connect(self):
                self.connect_calls += 1
                return {
                    "id": "cap-812",
                    "done": True,
                    "accepted": False,
                    "active_actions": [],
                    "engine_context": {},
                    "error": "grant token rejected",
                }

        create_block_called = {"value": False}

        def _forbidden_create_block(*args, **kwargs):
            create_block_called["value"] = True
            raise AssertionError("_create_block must not run when capability auth fails")

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-812")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", "/tmp/rs-run812.sock")
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *args, **kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda interval=5.0: None)
        monkeypatch.setattr(worker, "_heartbeat_stop", threading.Event())
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(worker._support, "_create_block", _forbidden_create_block)
        monkeypatch.setattr(sys, "stdin", io.StringIO(envelope.model_dump_json()))
        captured_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured_stdout)

        with pytest.raises(SystemExit) as exc_info:
            worker.main()

        result_env = ResultEnvelope.model_validate_json(captured_stdout.getvalue().strip())

        assert exc_info.value.code == 1
        assert len(FakeIPCClient.instances) == 1
        assert FakeIPCClient.instances[0].connect_calls == 1
        assert create_block_called["value"] is False
        assert result_env.error is not None
        assert "IPC auth failed" in result_env.error

    def test_assertion_main_uses_connect_handshake_before_assertion_execution(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import worker

        envelope = _make_context_envelope(
            block_id="assertion_auth_ok",
            block_type="assertion",
            block_config={
                "assertion": {"type": "llm_judge", "config": {"rubric": "strict"}},
                "output_to_grade": "Candidate response",
                "judge_soul": {
                    "id": "judge_soul_1",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
        )

        class FakeIPCClient:
            instances: list["FakeIPCClient"] = []

            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path
                self.connect_calls = 0
                self.request_calls: list[str] = []
                FakeIPCClient.instances.append(self)

            async def connect(self):
                self.connect_calls += 1
                return {
                    "id": "cap-812",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["llm_call", "tool_call"],
                    "engine_context": {},
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                self.request_calls.append(action)
                return {"output": "unused"}

            async def request_stream(self, action: str, payload: dict[str, object]):
                self.request_calls.append(action)
                yield {
                    "content": "unused",
                    "cost_usd": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls": [],
                    "finish_reason": "stop",
                }

        class _FakeAssertionBlock:
            def __init__(self, block_id: str) -> None:
                self._block_id = block_id

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                return BlockOutput(output="assertion-ok", exit_handle="done")

        def _fake_create_block(envelope_arg, soul_arg, runner_arg):
            assert envelope_arg.block_type == "assertion"
            return _FakeAssertionBlock(envelope_arg.block_id)

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-812")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", "/tmp/rs-run812.sock")
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *args, **kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda interval=5.0: None)
        monkeypatch.setattr(worker, "_heartbeat_stop", threading.Event())
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(worker._support, "_create_block", _fake_create_block)
        monkeypatch.setattr(sys, "stdin", io.StringIO(envelope.model_dump_json()))
        captured_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured_stdout)

        with pytest.raises(SystemExit) as exc_info:
            worker.main()

        result_env = ResultEnvelope.model_validate_json(captured_stdout.getvalue().strip())

        assert exc_info.value.code == 0
        assert len(FakeIPCClient.instances) == 1
        assert FakeIPCClient.instances[0].connect_calls == 1
        assert "capability_negotiation" not in FakeIPCClient.instances[0].request_calls
        assert result_env.error is None
        assert result_env.output == "assertion-ok"


# ==============================================================================
# AC9: Missing RUNSIGHT_IPC_SOCKET → exit 1 with clear error
# ==============================================================================


class TestWorkerMissingIpcSocket:
    """Missing RUNSIGHT_IPC_SOCKET must exit 1 with error in ResultEnvelope."""

    def test_missing_ipc_socket_exits_nonzero(self):
        """Worker exits with code 1 when RUNSIGHT_IPC_SOCKET is absent."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_IPC_SOCKET", None)
        env_override["RUNSIGHT_GRANT_TOKEN"] = "grant-token-123"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope, not just a Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for missing IPC socket"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_missing_ipc_socket_has_error_in_result(self):
        """ResultEnvelope on stdout describes the missing IPC socket."""
        envelope = _make_context_envelope()
        env_override = os.environ.copy()
        env_override.pop("RUNSIGHT_IPC_SOCKET", None)
        env_override["RUNSIGHT_GRANT_TOKEN"] = "grant-token-123"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input=envelope.model_dump_json(),
            capture_output=True,
            text=True,
            env=env_override,
            timeout=10,
        )
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout even on env error"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_IPC_SOCKET" in result_env.error


# ==============================================================================
# AC10: Exit 0 on success, exit 1 on error
# ==============================================================================


class TestWorkerExitCodes:
    """Worker must exit 0 on success and 1 on error."""

    def test_error_exits_with_code_1(self):
        """An error during execution produces exit code 1."""
        # Invalid block type should cause an error
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        assert result.returncode == 1, (
            f"Expected exit 1 on error, got {result.returncode}. "
            f"stdout={result.stdout}, stderr={result.stderr}"
        )
        # Must produce a proper ResultEnvelope, not a raw Python traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for error exit"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None

    def test_result_envelope_on_stdout_for_any_exit(self):
        """Regardless of exit code, stdout must contain a valid ResultEnvelope."""
        envelope = _make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = _run_worker(envelope)
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        # Must parse as valid ResultEnvelope
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.block_id == "blk_1"


# ==============================================================================
# AC3 supplement: stdin → ContextEnvelope parsing
# ==============================================================================


class TestWorkerEnvelopeParsing:
    """Worker must read stdin and parse as ContextEnvelope."""

    def test_parse_context_envelope_from_json(self):
        """Worker has a function to parse ContextEnvelope from JSON string."""
        from runsight_core.isolation.worker_support import parse_context_envelope

        envelope = _make_context_envelope()
        parsed = parse_context_envelope(envelope.model_dump_json())
        assert isinstance(parsed, ContextEnvelope)
        assert parsed.block_id == "blk_1"

    def test_invalid_json_produces_error_result(self):
        """Malformed JSON input yields exit 1 with error in ResultEnvelope."""
        env = os.environ.copy()
        env["RUNSIGHT_GRANT_TOKEN"] = "grant-token-123"
        env["RUNSIGHT_IPC_SOCKET"] = "/tmp/test.sock"
        result = subprocess.run(
            [sys.executable, "-m", "runsight_core.isolation.worker"],
            input="this is not json",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 1
        # Must produce a ResultEnvelope with error info, not a raw traceback
        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout for invalid JSON"
        result_env = ResultEnvelope.model_validate_json(stdout)
        assert result_env.error is not None


# ==============================================================================
# Soul reconstruction from SoulEnvelope
# ==============================================================================


class TestWorkerSoulReconstruction:
    """Worker must reconstruct a Soul primitive from SoulEnvelope."""

    def test_reconstruct_soul_from_envelope(self):
        """Worker converts SoulEnvelope to a runsight_core.primitives.Soul."""
        from runsight_core.isolation.worker_support import reconstruct_soul

        soul_env = SoulEnvelope(
            id="soul_1",
            name="Tester",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        )
        soul = reconstruct_soul(soul_env)
        from runsight_core.primitives import Soul

        assert isinstance(soul, Soul)
        assert soul.id == "soul_1"
        assert soul.role == "Tester"
        assert soul.system_prompt == "You test things."
        assert soul.model_name == "gpt-4o"
        assert soul.max_tool_iterations == 5

    def test_reconstruct_soul_attaches_resolved_tools(self):
        """Worker should attach IPC-backed resolved_tools to the reconstructed Soul."""
        from runsight_core.isolation.worker_support import reconstruct_soul
        from runsight_core.tools import ToolInstance

        soul_env = SoulEnvelope(
            id="soul_1",
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


# ==============================================================================
# Scoped WorkflowState construction
# ==============================================================================


class TestWorkerScopedState:
    """Worker must construct a scoped WorkflowState from envelope data."""

    def test_build_scoped_state(self):
        """Worker builds a WorkflowState from scoped_results and shared_memory."""
        from runsight_core.isolation.worker_support import build_scoped_state

        envelope = _make_context_envelope(
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
