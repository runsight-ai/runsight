"""Interceptor registry contract behavior."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.real_subprocess_isolation


class TestInterceptorRegistryContract:
    """Interceptor registry applies request/response/stream hooks in deterministic order."""

    def test_interceptor_registry_and_protocol_symbols_exist(self):
        from runsight_core.isolation import interceptors as interceptors_module

        assert getattr(interceptors_module, "IPCInterceptor", None) is not None
        assert getattr(interceptors_module, "InterceptorRegistry", None) is not None

    @pytest.mark.asyncio
    async def test_on_request_starts_with_fresh_empty_context(self):
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        observed: list[dict[str, Any]] = []

        class BudgetLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                observed.append(dict(engine_context))
                assert action == "http"
                assert payload == {"url": "https://fixture.test"}
                engine_context["budget_remaining_usd"] = 12.5
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        class ObserverLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                observed.append(dict(engine_context))
                engine_context["trace_id"] = "registry-chain-trace"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(BudgetLikeInterceptor())
        registry.register(ObserverLikeInterceptor())

        context = await registry.run_on_request("http", {"url": "https://fixture.test"}, {})
        assert observed[0] == {}
        assert observed[1] == {"budget_remaining_usd": 12.5}
        assert context == {
            "budget_remaining_usd": 12.5,
            "trace_id": "registry-chain-trace",
        }

    @pytest.mark.asyncio
    async def test_request_forward_response_reverse_and_chunk_forward_order(self):
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        call_order: list[str] = []

        class BudgetLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("budget.request")
                engine_context["budget"] = "set"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("budget.response")
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                call_order.append("budget.chunk")
                return engine_context

        class ObserverLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("observer.request")
                engine_context["observer"] = "set"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                call_order.append("observer.response")
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                call_order.append("observer.chunk")
                return engine_context

        registry.register(BudgetLikeInterceptor())
        registry.register(ObserverLikeInterceptor())

        context: dict[str, Any] = {}
        context = await registry.run_on_request("delegate", {"task": "do work"}, context)
        context = await registry.run_on_stream_chunk("delegate", {"chunk": 1}, context)
        context = await registry.run_on_response("delegate", {"final": "ok"}, context)

        assert call_order == [
            "budget.request",
            "observer.request",
            "budget.chunk",
            "observer.chunk",
            "observer.response",
            "budget.response",
        ]
        assert context == {"budget": "set", "observer": "set"}

    @pytest.mark.asyncio
    async def test_empty_registry_is_passthrough(self):
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        ctx: dict[str, Any] = {}
        after_request = await registry.run_on_request("http", {"url": "x"}, ctx)
        after_chunk = await registry.run_on_stream_chunk("http", {"chunk": "a"}, after_request)
        after_response = await registry.run_on_response("http", {"status": 200}, after_chunk)
        assert after_response == {}
