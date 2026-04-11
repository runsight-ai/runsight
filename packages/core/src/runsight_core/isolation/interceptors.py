"""IPC interceptors for request lifecycle hooks (RUN-818).

Extracted from ipc.py to give interceptor definitions a dedicated home,
separate from the IPCServer / IPCClient implementation.
"""

from __future__ import annotations

import importlib
import logging
import time
from typing import Any, Protocol

from runsight_core.budget_enforcement import BudgetSession
from runsight_core.isolation.ipc_models import _current_ipc_request_id

logger = logging.getLogger(__name__)


class IPCInterceptor(Protocol):
    """Interceptor hook contract for IPC request lifecycle events."""

    async def on_request(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def on_response(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def on_stream_chunk(
        self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]: ...


class InterceptorRegistry:
    """Registry that executes IPC interceptors using chain-of-responsibility order."""

    def __init__(self) -> None:
        self._interceptors: list[IPCInterceptor] = []

    def register(self, interceptor: IPCInterceptor) -> None:
        self._interceptors.append(interceptor)

    async def run_on_request(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        for interceptor in self._interceptors:
            engine_context = await interceptor.on_request(action, payload, engine_context)
        return engine_context

    async def run_on_response(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        for interceptor in reversed(self._interceptors):
            engine_context = await interceptor.on_response(action, payload, engine_context)
        return engine_context

    async def run_on_stream_chunk(
        self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        for interceptor in self._interceptors:
            engine_context = await interceptor.on_stream_chunk(action, chunk, engine_context)
        return engine_context


class BudgetInterceptor:
    """Interceptor that enforces and accrues cross-process budget usage."""

    def __init__(
        self,
        *,
        session: BudgetSession | None = None,
        budget_session: BudgetSession | None = None,
        block_id: str | None = None,
    ) -> None:
        self._session = session or budget_session
        if self._session is None:
            raise TypeError("BudgetInterceptor requires a BudgetSession")
        self._block_id = block_id

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _remaining_context(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if self._session.cost_cap_usd is not None:
            context["budget_remaining_usd"] = self._session.cost_cap_usd - self._session.cost_usd
        if self._session.token_cap is not None:
            context["budget_remaining_tokens"] = self._session.token_cap - self._session.tokens
        return context

    async def on_request(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        if action != "capability_negotiation":
            self._session.check_or_raise(block_id=self._block_id)
        engine_context.update(self._remaining_context())
        return engine_context

    async def on_response(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        if action != "capability_negotiation":
            self._session.accrue(
                cost_usd=self._to_float(payload.get("cost_usd")),
                tokens=self._to_int(payload.get("total_tokens")),
            )
        engine_context.update(self._remaining_context())
        return engine_context

    async def on_stream_chunk(
        self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        if action != "capability_negotiation":
            tokens = self._to_int(chunk.get("tokens", chunk.get("total_tokens")))
            self._session.accrue(
                cost_usd=self._to_float(chunk.get("cost_usd")),
                tokens=tokens,
            )
        engine_context.update(self._remaining_context())
        return engine_context


class ObserverInterceptor:
    """Interceptor that records IPC action tracing with optional OTel support."""

    def __init__(self, *, tracer: Any | None = None, block_id: str | None = None) -> None:
        self._tracer = tracer if tracer is not None else self._resolve_tracer()
        self._block_id = block_id
        self._active_spans: dict[str, tuple[Any, float]] = {}

    @staticmethod
    def _span_key(action: str, engine_context: dict[str, Any]) -> str:
        request_id = engine_context.get("ipc.request_id") or _current_ipc_request_id.get()
        return f"{action}:{request_id}" if request_id else action

    def _emit_log(
        self,
        *,
        event: str,
        action: str,
        engine_context: dict[str, Any],
        payload: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        structured_data: dict[str, Any] = {
            "observer_event": event,
            "action": action,
            "block_id": self._block_id,
            "trace_id": engine_context.get("trace_id"),
            "span_id": engine_context.get("span_id"),
            "trace_parent_id": engine_context.get("trace.parent_id"),
        }
        if payload is not None:
            structured_data["model"] = payload.get("model")
            structured_data["cost_usd"] = payload.get("cost_usd")
            structured_data["total_tokens"] = payload.get("total_tokens")
            structured_data["tokens"] = payload.get("tokens")
            structured_data["error"] = payload.get("error")
        request_id = engine_context.get("ipc.request_id") or _current_ipc_request_id.get()
        if request_id is not None:
            structured_data["ipc_request_id"] = request_id
        if duration_ms is not None:
            structured_data["duration_ms"] = duration_ms
        logger.info("observer.ipc", extra=structured_data)

    @staticmethod
    def _resolve_tracer() -> Any | None:
        try:
            trace_module = importlib.import_module("opentelemetry.trace")
            return trace_module.get_tracer("runsight_core.isolation.ipc")
        except Exception:
            return None

    @staticmethod
    def _normalize_id(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, int):
            return f"{value:x}"
        return str(value)

    def _start_span(
        self,
        action: str,
        payload: dict[str, Any],
        engine_context: dict[str, Any],
    ) -> Any | None:
        if self._tracer is None:
            return None

        attributes: dict[str, Any] = {"action": action}
        if self._block_id is not None:
            attributes["block_id"] = self._block_id
        if payload.get("model") is not None:
            attributes["model"] = payload.get("model")
        parent_id = engine_context.get("trace.parent_id")
        if parent_id is not None:
            attributes["trace.parent_id"] = parent_id

        try:
            if hasattr(self._tracer, "start_span"):
                return self._tracer.start_span(name=action, attributes=attributes)
            if hasattr(self._tracer, "start_as_current_span"):
                span_ctx = self._tracer.start_as_current_span(name=action, attributes=attributes)
                if hasattr(span_ctx, "__enter__"):
                    return span_ctx.__enter__()
        except Exception:
            return None
        return None

    async def on_request(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        span = self._start_span(action, payload, engine_context)
        if span is None:
            self._emit_log(
                event="ipc_request",
                action=action,
                payload=payload,
                engine_context=engine_context,
            )
            return engine_context

        self._active_spans[self._span_key(action, engine_context)] = (span, time.monotonic())
        try:
            span_ctx = span.get_span_context()
        except Exception:
            return engine_context

        trace_id = self._normalize_id(getattr(span_ctx, "trace_id", None))
        span_id = self._normalize_id(getattr(span_ctx, "span_id", None))
        if trace_id is not None:
            engine_context["trace_id"] = trace_id
        if span_id is not None:
            engine_context["span_id"] = span_id
        self._emit_log(
            event="ipc_request",
            action=action,
            payload=payload,
            engine_context=engine_context,
        )
        return engine_context

    async def on_response(
        self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        span_record = self._active_spans.pop(self._span_key(action, engine_context), None)
        if span_record is None:
            self._emit_log(
                event="ipc_response",
                action=action,
                payload=payload,
                engine_context=engine_context,
            )
            return engine_context

        span, started_at = span_record
        duration_ms = (time.monotonic() - started_at) * 1000.0
        try:
            if "cost_usd" in payload:
                span.set_attribute("cost_usd", payload.get("cost_usd"))
            if "total_tokens" in payload:
                span.set_attribute("total_tokens", payload.get("total_tokens"))
            error_value = payload.get("error")
            if error_value is not None:
                span.set_attribute("error", error_value)
            span.set_attribute("duration_ms", duration_ms)
            span.end()
        except Exception:
            self._emit_log(
                event="ipc_response",
                action=action,
                payload=payload,
                engine_context=engine_context,
                duration_ms=duration_ms,
            )
            return engine_context
        self._emit_log(
            event="ipc_response",
            action=action,
            payload=payload,
            engine_context=engine_context,
            duration_ms=duration_ms,
        )
        return engine_context

    async def on_stream_chunk(
        self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
    ) -> dict[str, Any]:
        span_record = self._active_spans.get(self._span_key(action, engine_context))
        if span_record is None:
            self._emit_log(
                event="ipc_stream_chunk",
                action=action,
                payload=chunk,
                engine_context=engine_context,
            )
            return engine_context

        span, _ = span_record
        try:
            span.add_event(
                "stream.chunk",
                {
                    "total_tokens": chunk.get("total_tokens"),
                    "tokens": chunk.get("tokens"),
                },
            )
        except Exception:
            self._emit_log(
                event="ipc_stream_chunk",
                action=action,
                payload=chunk,
                engine_context=engine_context,
            )
            return engine_context
        self._emit_log(
            event="ipc_stream_chunk",
            action=action,
            payload=chunk,
            engine_context=engine_context,
        )
        return engine_context
