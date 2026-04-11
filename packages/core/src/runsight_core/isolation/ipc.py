"""IPC server and client using Unix sockets with NDJSON framing (ISO-002)."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import socket
import time
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from runsight_core.budget_enforcement import BudgetKilledException, BudgetSession

HandlerResult = Awaitable[dict[str, Any]] | AsyncIterable[dict[str, Any]]
Handler = Callable[[dict[str, Any]], HandlerResult]
logger = logging.getLogger(__name__)

RPC_ALLOWLIST = frozenset(
    {
        "capability_negotiation",
        "delegate",
        "file_io",
        "http",
        "llm_call",
        "simple",
        "stream",
        "tool_call",
        "write_artifact",
    }
)


class GrantToken(BaseModel):
    """Single-use grant token for subprocess->engine IPC authentication."""

    block_id: str
    token: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = Field(default_factory=time.monotonic)
    ttl_seconds: float = 30.0
    consumed: bool = False

    def is_expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl_seconds

    def consume(self) -> bool:
        if self.consumed:
            return False
        if self.is_expired():
            return False
        self.consumed = True
        return True


class IPCRequest(BaseModel):
    """Request envelope sent from engine process to worker process."""

    model_config = ConfigDict(extra="forbid")

    id: str
    action: str
    payload: dict[str, Any]


class CapabilityRequest(BaseModel):
    """Dedicated startup capability negotiation request."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["capability_negotiation"] = "capability_negotiation"
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    grant_token: str
    supported_actions: list[str]
    worker_version: str


class CapabilityResponse(BaseModel):
    """Dedicated startup capability negotiation response."""

    id: str
    done: bool = True
    accepted: bool
    active_actions: list[str]
    engine_context: dict[str, Any]
    error: str | None


class IPCResponseFrame(BaseModel):
    """Streamed response frame sent from worker process to engine process."""

    id: str
    done: bool
    payload: Any | None
    engine_context: dict[str, Any] | None
    error: str | None


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
            self._session.check_or_raise(block_id=self._block_id)
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
            self._session.check_or_raise(block_id=self._block_id)
        engine_context.update(self._remaining_context())
        return engine_context


class ObserverInterceptor:
    """Interceptor that records IPC action tracing with optional OTel support."""

    def __init__(self, *, tracer: Any | None = None, block_id: str | None = None) -> None:
        self._tracer = tracer if tracer is not None else self._resolve_tracer()
        self._block_id = block_id
        self._active_spans: dict[str, tuple[Any, float]] = {}

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

        self._active_spans[action] = (span, time.monotonic())
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
        span_record = self._active_spans.pop(action, None)
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
        span_record = self._active_spans.get(action)
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


def _is_async_iterable(value: Any) -> bool:
    return hasattr(value, "__aiter__")


class IPCServer:
    """Async Unix socket server that dispatches NDJSON requests to handlers.

    Accepts an already-bound socket object (does not create or bind one).
    """

    def __init__(
        self,
        *,
        sock: socket.socket,
        handlers: dict[str, Handler],
        registry: InterceptorRegistry | None = None,
        grant_token: GrantToken | None = None,
    ) -> None:
        if not isinstance(sock, socket.socket):
            raise TypeError("sock must be a socket.socket instance, not a path string")
        self._sock = sock
        self._handlers = handlers
        self._registry = registry or InterceptorRegistry()
        self._grant_token = grant_token
        self._server: asyncio.AbstractServer | None = None
        self._shutdown_event = asyncio.Event()
        # Capture the socket path for cleanup
        try:
            self._sock_path: str | None = sock.getsockname()
        except OSError:
            self._sock_path = None

    async def _write_frame(self, writer: asyncio.StreamWriter, frame: IPCResponseFrame) -> None:
        line = json.dumps(frame.model_dump(), separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

    async def _write_capability_response(
        self,
        writer: asyncio.StreamWriter,
        response: CapabilityResponse,
    ) -> None:
        line = json.dumps(response.model_dump(), separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

    async def _negotiate_capabilities(
        self,
        request: CapabilityRequest,
    ) -> CapabilityResponse:
        if self._grant_token is None:
            return CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token not configured",
            )

        if request.grant_token != self._grant_token.token:
            return CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: invalid grant token",
            )

        if self._grant_token.is_expired():
            return CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token expired",
            )

        if self._grant_token.consumed:
            return CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token consumed",
            )

        if not self._grant_token.consume():
            return CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token rejected",
            )

        active_actions = [
            action
            for action in request.supported_actions
            if action in RPC_ALLOWLIST and action in self._handlers
        ]
        engine_context: dict[str, Any] = {
            "budget_remaining_usd": 0.0,
            "trace_id": uuid.uuid4().hex,
            "run_id": uuid.uuid4().hex,
            "block_id": self._grant_token.block_id,
        }
        engine_context = await self._registry.run_on_request(
            request.action,
            {
                "supported_actions": request.supported_actions,
                "worker_version": request.worker_version,
            },
            engine_context,
        )
        engine_context = await self._registry.run_on_response(
            request.action,
            {"accepted": True, "active_actions": active_actions},
            engine_context,
        )

        return CapabilityResponse(
            id=request.id,
            accepted=True,
            active_actions=active_actions,
            engine_context=engine_context,
            error=None,
        )

    async def serve(self) -> None:
        """Start accepting connections on the pre-bound socket."""
        self._sock.setblocking(False)
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            sock=self._sock,
        )
        # Wait until shutdown is requested
        await self._shutdown_event.wait()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Process NDJSON lines from a single client connection."""
        authenticated = False

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                raw_request: Any
                try:
                    raw_request = json.loads(line)
                except json.JSONDecodeError as exc:
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id="",
                            done=True,
                            payload=None,
                            engine_context=None,
                            error=f"invalid request frame: {exc.msg}",
                        ),
                    )
                    continue

                if not isinstance(raw_request, dict):
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id="",
                            done=True,
                            payload=None,
                            engine_context=None,
                            error="invalid request frame: expected JSON object",
                        ),
                    )
                    continue

                request_id = str(raw_request.get("id", ""))

                if not authenticated:
                    action = str(raw_request.get("action", ""))
                    if action != "capability_negotiation":
                        await self._write_frame(
                            writer,
                            IPCResponseFrame(
                                id=request_id,
                                done=True,
                                payload=None,
                                engine_context=None,
                                error="authentication required: perform capability_negotiation first",
                            ),
                        )
                        continue

                    try:
                        capability_request = CapabilityRequest.model_validate(raw_request)
                    except Exception as exc:
                        await self._write_capability_response(
                            writer,
                            CapabilityResponse(
                                id=request_id,
                                accepted=False,
                                active_actions=[],
                                engine_context={},
                                error=f"invalid capability request: {exc}",
                            ),
                        )
                        continue

                    capability_response = await self._negotiate_capabilities(capability_request)
                    await self._write_capability_response(writer, capability_response)
                    if capability_response.accepted:
                        authenticated = True
                    continue

                try:
                    request = IPCRequest.model_validate(raw_request)
                except Exception as exc:
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id=request_id,
                            done=True,
                            payload=None,
                            engine_context=None,
                            error=f"invalid request frame: {exc}",
                        ),
                    )
                    continue

                engine_context: dict[str, Any] = {}
                try:
                    engine_context = await self._registry.run_on_request(
                        request.action,
                        request.payload,
                        engine_context,
                    )
                except BudgetKilledException as exc:
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=None,
                            engine_context=engine_context,
                            error=str(exc),
                        ),
                    )
                    continue

                if request.action not in RPC_ALLOWLIST:
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=None,
                            engine_context=engine_context,
                            error=f"unsupported action: {request.action}",
                        ),
                    )
                    continue

                handler = self._handlers.get(request.action)
                try:
                    if handler is None:
                        await self._write_frame(
                            writer,
                            IPCResponseFrame(
                                id=request.id,
                                done=True,
                                payload=None,
                                engine_context=engine_context,
                                error=f"unsupported action: {request.action}",
                            ),
                        )
                        continue

                    result_or_stream = handler(request.payload)
                    if _is_async_iterable(result_or_stream):
                        async for chunk in result_or_stream:
                            engine_context = await self._registry.run_on_stream_chunk(
                                request.action,
                                chunk,
                                engine_context,
                            )
                            await self._write_frame(
                                writer,
                                IPCResponseFrame(
                                    id=request.id,
                                    done=False,
                                    payload=chunk,
                                    engine_context=engine_context,
                                    error=None,
                                ),
                            )
                        engine_context = await self._registry.run_on_response(
                            request.action,
                            {},
                            engine_context,
                        )
                        await self._write_frame(
                            writer,
                            IPCResponseFrame(
                                id=request.id,
                                done=True,
                                payload=None,
                                engine_context=engine_context,
                                error=None,
                            ),
                        )
                        continue

                    if asyncio.iscoroutine(result_or_stream) or isinstance(
                        result_or_stream, Awaitable
                    ):
                        payload = await result_or_stream
                    else:
                        payload = result_or_stream

                    engine_context = await self._registry.run_on_response(
                        request.action,
                        payload,
                        engine_context,
                    )
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=payload,
                            engine_context=engine_context,
                            error=None,
                        ),
                    )
                except Exception as exc:
                    await self._write_frame(
                        writer,
                        IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=None,
                            engine_context=engine_context,
                            error=str(exc),
                        ),
                    )
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async def shutdown(self) -> None:
        """Stop the server and release the socket."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        # Close the underlying socket so new connections are refused
        try:
            self._sock.close()
        except OSError:
            pass
        # Remove the socket file from disk
        if self._sock_path:
            try:
                os.unlink(self._sock_path)
            except OSError:
                pass
        self._shutdown_event.set()


class IPCClient:
    """Async Unix socket client that sends NDJSON requests and reads correlated responses."""

    def __init__(self, *, socket_path: str) -> None:
        self._socket_path = socket_path
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._closed = False
        self._grant_token = os.environ.get("RUNSIGHT_GRANT_TOKEN", "")
        self._supported_actions = ["llm_call", "tool_call", "http", "file_io"]
        self._worker_version = "worker-396"
        self._active_actions: list[str] = []
        self._initial_engine_context: dict[str, Any] = {}

    async def connect(self) -> CapabilityResponse:
        """Open a connection to the IPC socket."""
        self._reader, self._writer = await asyncio.open_unix_connection(self._socket_path)
        capability_request = CapabilityRequest(
            grant_token=self._grant_token,
            supported_actions=list(self._supported_actions),
            worker_version=self._worker_version,
        )
        line = json.dumps(capability_request.model_dump(), separators=(",", ":")) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()

        raw_response = await self._reader.readline()
        if not raw_response:
            self._closed = True
            raise ConnectionError("IPC socket disconnected during capability negotiation")
        try:
            response = CapabilityResponse.model_validate_json(raw_response)
        except Exception as exc:
            raise ConnectionError("invalid capability response") from exc

        self._active_actions = list(response.active_actions)
        self._initial_engine_context = dict(response.engine_context)
        return response

    async def _read_response_line(self) -> tuple[bool, Any, str | None]:
        if self._reader is None:
            raise ConnectionError("IPC client is not connected")

        raw_response = await self._reader.readline()
        if not raw_response:
            self._closed = True
            raise ConnectionError("IPC socket disconnected")

        response: Any
        try:
            response = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise ConnectionError("invalid response frame") from exc

        try:
            frame = IPCResponseFrame.model_validate(response)
        except Exception as exc:
            raise ConnectionError("invalid response frame") from exc

        return frame.done, frame.payload, frame.error

    def _build_request_frame(self, action: str, payload: dict[str, Any]) -> IPCRequest:
        return IPCRequest(
            id=str(uuid.uuid4()),
            action=action,
            payload=payload,
        )

    async def _send_request_frame(self, request: IPCRequest) -> None:
        if self._writer is None:
            raise ConnectionError("IPC client is not connected")
        line = json.dumps(request.model_dump(), separators=(",", ":")) + "\n"
        self._writer.write(line.encode())
        await self._writer.drain()

    async def request(
        self,
        action: str,
        payload: dict[str, Any],
    ) -> Any:
        """Send an NDJSON request and return the final payload frame."""
        if self._closed:
            raise ConnectionError("IPC client is closed")
        if action == "capability_negotiation":
            raise ValueError("capability_negotiation is only supported via connect()")

        if self._writer is None or self._reader is None:
            await self.connect()

        try:
            request = self._build_request_frame(action, payload)
            await self._send_request_frame(request)

            while True:
                done, frame_payload, frame_error = await self._read_response_line()
                if frame_error is not None:
                    return {"error": frame_error}
                if done:
                    return frame_payload
        except (ConnectionResetError, BrokenPipeError) as exc:
            self._closed = True
            raise ConnectionError("IPC socket disconnected") from exc

    async def request_stream(
        self,
        action: str,
        payload: dict[str, Any],
    ):
        """Send an NDJSON request and yield non-final payload frames."""
        if self._closed:
            raise ConnectionError("IPC client is closed")
        if action == "capability_negotiation":
            raise ValueError("capability_negotiation is only supported via connect()")

        if self._writer is None or self._reader is None:
            await self.connect()

        request = self._build_request_frame(action, payload)

        try:
            await self._send_request_frame(request)

            while True:
                done, frame_payload, frame_error = await self._read_response_line()
                if frame_error is not None:
                    raise ConnectionError(frame_error)
                if done:
                    break
                yield frame_payload
        except (ConnectionResetError, BrokenPipeError) as exc:
            self._closed = True
            raise ConnectionError("IPC socket disconnected") from exc

    async def close(self) -> None:
        """Close the connection."""
        self._closed = True
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
