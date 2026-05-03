"""Worker proxied LLM client behavior."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.real_subprocess_isolation


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
