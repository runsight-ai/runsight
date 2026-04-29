"""ISO-002 IPC observer interceptor tests."""

from __future__ import annotations

from typing import Any

import pytest
from isolation_ipc_helpers import (
    _make_observer_interceptor,
)


class TestObserverInterceptorContract:
    """RUN-397: ObserverInterceptor OTel span lifecycle + trace context propagation."""

    @pytest.mark.asyncio
    async def test_observer_interceptor_creates_span_and_records_response_metrics(self):
        from runsight_core.isolation import interceptors as interceptors_module

        class FakeSpanContext:
            def __init__(self, trace_id: int, span_id: int):
                self.trace_id = trace_id
                self.span_id = span_id

        class FakeSpan:
            def __init__(self) -> None:
                self.attributes: dict[str, Any] = {}
                self.events: list[tuple[str, dict[str, Any] | None]] = []
                self.ended = False
                self._ctx = FakeSpanContext(trace_id=0xABCDEF, span_id=0x123456)

            def set_attribute(self, key: str, value: Any) -> None:
                self.attributes[key] = value

            def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
                self.events.append((name, attributes))

            def get_span_context(self) -> FakeSpanContext:
                return self._ctx

            def end(self) -> None:
                self.ended = True

        class _SpanContextManager:
            def __init__(self, span: FakeSpan):
                self._span = span

            def __enter__(self) -> FakeSpan:
                return self._span

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        class FakeTracer:
            def __init__(self) -> None:
                self.started: list[tuple[str, dict[str, Any] | None, FakeSpan]] = []

            def start_span(
                self,
                name: str,
                attributes: dict[str, Any] | None = None,
            ) -> FakeSpan:
                span = FakeSpan()
                if attributes:
                    span.attributes.update(attributes)
                self.started.append((name, attributes, span))
                return span

            def start_as_current_span(
                self,
                name: str,
                attributes: dict[str, Any] | None = None,
            ) -> _SpanContextManager:
                span = self.start_span(name=name, attributes=attributes)
                return _SpanContextManager(span)

        tracer = FakeTracer()
        observer = _make_observer_interceptor(
            interceptors_module,
            tracer=tracer,
            block_id="run397-block",
        )

        engine_context = {"trace.parent_id": "parent-span-42"}
        engine_context = await observer.on_request(
            "llm_call",
            {"model": "claude-sonnet-4-20250514"},
            engine_context,
        )
        engine_context = await observer.on_response(
            "llm_call",
            {"cost_usd": 0.10, "total_tokens": 81, "error": "rate limited"},
            engine_context,
        )

        assert engine_context["trace.parent_id"] == "parent-span-42"
        assert "trace_id" in engine_context
        assert "span_id" in engine_context
        assert len(tracer.started) == 1
        _, _, span = tracer.started[0]
        assert span.ended is True
        assert 0.10 in span.attributes.values()
        assert 81 in span.attributes.values()
        assert any("error" in str(key).lower() for key in span.attributes)

    @pytest.mark.asyncio
    async def test_observer_interceptor_records_stream_chunk_events(self):
        from runsight_core.isolation import interceptors as interceptors_module

        class FakeSpanContext:
            def __init__(self):
                self.trace_id = 0x111111
                self.span_id = 0x222222

        class FakeSpan:
            def __init__(self) -> None:
                self.attributes: dict[str, Any] = {}
                self.events: list[tuple[str, dict[str, Any] | None]] = []
                self._ctx = FakeSpanContext()

            def set_attribute(self, key: str, value: Any) -> None:
                self.attributes[key] = value

            def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
                self.events.append((name, attributes))

            def get_span_context(self) -> FakeSpanContext:
                return self._ctx

            def end(self) -> None:
                return None

        class FakeTracer:
            def __init__(self) -> None:
                self.span = FakeSpan()

            def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> FakeSpan:
                if attributes:
                    self.span.attributes.update(attributes)
                return self.span

        tracer = FakeTracer()
        observer = _make_observer_interceptor(
            interceptors_module, tracer=tracer, block_id="run397-stream"
        )

        engine_context: dict[str, Any] = {}
        engine_context = await observer.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        await observer.on_stream_chunk(
            "llm_call",
            {"chunk": 1, "total_tokens": 10},
            engine_context,
        )
        await observer.on_stream_chunk(
            "llm_call",
            {"chunk": 2, "total_tokens": 21},
            engine_context,
        )

        assert len(tracer.span.events) >= 2

    @pytest.mark.asyncio
    async def test_observer_interceptor_keys_active_spans_by_request_id(self):
        from runsight_core.isolation import interceptors as interceptors_module

        class FakeSpanContext:
            def __init__(self, index: int):
                self.trace_id = 0x1000 + index
                self.span_id = 0x2000 + index

        class FakeSpan:
            def __init__(self, index: int) -> None:
                self.ended = False
                self._ctx = FakeSpanContext(index)

            def set_attribute(self, key: str, value: Any) -> None:
                return None

            def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
                return None

            def get_span_context(self) -> FakeSpanContext:
                return self._ctx

            def end(self) -> None:
                self.ended = True

        class FakeTracer:
            def __init__(self) -> None:
                self.spans: list[FakeSpan] = []

            def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> FakeSpan:
                span = FakeSpan(len(self.spans) + 1)
                self.spans.append(span)
                return span

        tracer = FakeTracer()
        observer = _make_observer_interceptor(
            interceptors_module, tracer=tracer, block_id="run397-rid"
        )

        ctx_a = await observer.on_request(
            "llm_call",
            {"model": "gpt-4o-mini"},
            {"ipc.request_id": "req-a"},
        )
        ctx_b = await observer.on_request(
            "llm_call",
            {"model": "gpt-4o-mini"},
            {"ipc.request_id": "req-b"},
        )

        await observer.on_response("llm_call", {"cost_usd": 0.01}, ctx_a)
        await observer.on_response("llm_call", {"cost_usd": 0.02}, ctx_b)

        assert len(tracer.spans) == 2
        assert all(span.ended for span in tracer.spans)

    @pytest.mark.asyncio
    async def test_observer_interceptor_noop_when_tracer_unavailable(self):
        from runsight_core.isolation import interceptors as interceptors_module

        observer = _make_observer_interceptor(interceptors_module)
        engine_context: dict[str, Any] = {}

        request_ctx = await observer.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        stream_ctx = await observer.on_stream_chunk(
            "llm_call",
            {"chunk": 1, "total_tokens": 10},
            request_ctx,
        )
        response_ctx = await observer.on_response(
            "llm_call",
            {"cost_usd": 0.02, "total_tokens": 10},
            stream_ctx,
        )

        assert response_ctx == {}

    @pytest.mark.asyncio
    async def test_observer_interceptor_noop_when_opentelemetry_import_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import builtins
        import importlib

        from runsight_core.isolation import interceptors as interceptors_module

        real_import = builtins.__import__
        real_import_module = importlib.import_module

        def _failing_import(name: str, *args: Any, **kwargs: Any):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("simulated missing opentelemetry")
            return real_import(name, *args, **kwargs)

        def _failing_import_module(name: str, package: str | None = None):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("simulated missing opentelemetry")
            return real_import_module(name, package)

        monkeypatch.setattr(builtins, "__import__", _failing_import)
        monkeypatch.setattr(importlib, "import_module", _failing_import_module)

        observer = _make_observer_interceptor(
            interceptors_module,
            tracer=None,
            block_id="run397-no-otel",
        )
        request_ctx = await observer.on_request(
            "llm_call",
            {"model": "gpt-4o-mini"},
            {"trace.parent_id": "parent-397"},
        )
        response_ctx = await observer.on_response(
            "llm_call",
            {"cost_usd": 0.04, "total_tokens": 19},
            request_ctx,
        )

        assert response_ctx["trace.parent_id"] == "parent-397"
        assert "trace_id" not in response_ctx
        assert "span_id" not in response_ctx
