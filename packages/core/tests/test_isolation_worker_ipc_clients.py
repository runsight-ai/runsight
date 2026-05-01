"""Isolation worker IPC client and tool proxy contracts."""

from __future__ import annotations

import inspect
import io
import sys
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from isolation_worker_helpers import make_context_envelope, worker_socket_path
from runsight_core.isolation.envelope import ResultEnvelope, ToolDefEnvelope


class TestProxiedLLMClientContract:
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


class TestWorkerIPCToolStubs:
    """Tools must be routed through IPCClient, not executed locally."""

    def test_worker_creates_tool_stubs_from_envelope(self):
        """Worker converts ToolDefEnvelope list into IPC-backed tool stubs."""
        from runsight_core.isolation.worker_proxies import create_tool_stubs
        from runsight_core.tools import ToolInstance

        tool_defs = [
            ToolDefEnvelope(
                source="http",
                config={"url": "worker-fixture-url"},
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
                config={"url": "worker-fixture-url"},
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
                source="fixture/echo",
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
                source="fixture/echo",
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
                source="fixture/echo",
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


class TestWorkerSharedIPCClientContract:
    """Worker uses a single shared IPC client and expanded block type creation."""

    @pytest.mark.asyncio
    async def test_create_tool_stubs_uses_shared_authenticated_ipc_client(self):
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="fixture/echo",
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

        envelope = make_context_envelope(
            tools=[
                ToolDefEnvelope(
                    source="fixture/echo",
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
                    "id": "cap-worker-shared",
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

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-worker-shared")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", worker_socket_path("shared-ipc"))
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

        envelope = make_context_envelope(
            block_type=block_type,
            block_config={
                "eval_key": "result_a",
                "extract_field": "summary",
                "gate_soul": {
                    "id": "gate_quality_soul",
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
        assert block.gate_soul.id == "gate_quality_soul"

    @pytest.mark.parametrize("block_type", ["SynthesizeBlock", "synthesize"])
    def test_create_block_supports_synthesize_aliases_with_synthesizer_soul(
        self,
        block_type: str,
    ):
        from runsight_core.blocks.synthesize import SynthesizeBlock
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = make_context_envelope(
            block_type=block_type,
            block_config={
                "input_block_ids": ["a", "b"],
                "synthesizer_soul": {
                    "id": "synthesis_merge_soul",
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
        assert block.synthesizer_soul.id == "synthesis_merge_soul"

    @pytest.mark.parametrize("block_type", ["DispatchBlock", "dispatch"])
    def test_create_block_supports_dispatch_aliases(self, block_type: str):
        from runsight_core.blocks.dispatch import DispatchBlock
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = make_context_envelope(
            block_type=block_type,
            block_config={
                "branches": [
                    {
                        "exit_id": "branch_a",
                        "label": "Branch A",
                        "task_instruction": "Do A",
                        "soul": {
                            "id": "dispatch_branch_soul",
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
        assert block.branches[0].soul.id == "dispatch_branch_soul"
