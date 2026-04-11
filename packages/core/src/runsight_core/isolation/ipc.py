"""IPC server and client using Unix sockets with NDJSON framing (ISO-002)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import uuid
from collections.abc import Awaitable
from typing import Any

import runsight_core.isolation.interceptors as _interceptors
import runsight_core.isolation.ipc_models as _ipc_models
from runsight_core.budget_enforcement import (
    BudgetKilledException,
    budget_killed_exception_from_payload,
    budget_killed_exception_to_payload,
)

logger = logging.getLogger(__name__)


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
        handlers: dict[str, _ipc_models.Handler],
        registry: _interceptors.InterceptorRegistry | None = None,
        grant_token: _ipc_models.GrantToken | None = None,
    ) -> None:
        if not isinstance(sock, socket.socket):
            raise TypeError("sock must be a socket.socket instance, not a path string")
        self._sock = sock
        self._handlers = handlers
        self._registry = registry or _interceptors.InterceptorRegistry()
        self._grant_token = grant_token
        self._server: asyncio.AbstractServer | None = None
        self._shutdown_event = asyncio.Event()
        # Capture the socket path for cleanup
        try:
            self._sock_path: str | None = sock.getsockname()
        except OSError:
            self._sock_path = None

    async def _write_frame(
        self, writer: asyncio.StreamWriter, frame: _ipc_models.IPCResponseFrame
    ) -> None:
        line = json.dumps(frame.model_dump(), separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

    async def _write_capability_response(
        self,
        writer: asyncio.StreamWriter,
        response: _ipc_models.CapabilityResponse,
    ) -> None:
        line = json.dumps(response.model_dump(), separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

    async def _negotiate_capabilities(
        self,
        request: _ipc_models.CapabilityRequest,
    ) -> _ipc_models.CapabilityResponse:
        if self._grant_token is None:
            return _ipc_models.CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token not configured",
            )

        if request.grant_token != self._grant_token.token:
            return _ipc_models.CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: invalid grant token",
            )

        if not self._grant_token.consume():
            return _ipc_models.CapabilityResponse(
                id=request.id,
                accepted=False,
                active_actions=[],
                engine_context={},
                error="authentication failed: grant token rejected",
            )

        active_actions = [
            action
            for action in request.supported_actions
            if action in _ipc_models.RPC_ALLOWLIST and action in self._handlers
        ]
        engine_context: dict[str, Any] = {
            "budget_remaining_usd": 0.0,
            "trace_id": uuid.uuid4().hex,
            "run_id": uuid.uuid4().hex,
            "block_id": self._grant_token.block_id,
        }
        request_id_token = _ipc_models._current_ipc_request_id.set(request.id)
        try:
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
        finally:
            _ipc_models._current_ipc_request_id.reset(request_id_token)

        return _ipc_models.CapabilityResponse(
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
        active_actions: set[str] = set()

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
                        _ipc_models.IPCResponseFrame(
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
                        _ipc_models.IPCResponseFrame(
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
                            _ipc_models.IPCResponseFrame(
                                id=request_id,
                                done=True,
                                payload=None,
                                engine_context=None,
                                error="authentication required: perform capability_negotiation first",
                            ),
                        )
                        continue

                    try:
                        capability_request = _ipc_models.CapabilityRequest.model_validate(
                            raw_request
                        )
                    except Exception:
                        logger.exception("ipc.invalid_capability_request")
                        await self._write_capability_response(
                            writer,
                            _ipc_models.CapabilityResponse(
                                id=request_id,
                                accepted=False,
                                active_actions=[],
                                engine_context={},
                                error="invalid capability request",
                            ),
                        )
                        continue

                    capability_response = await self._negotiate_capabilities(capability_request)
                    await self._write_capability_response(writer, capability_response)
                    if capability_response.accepted:
                        authenticated = True
                        active_actions = set(capability_response.active_actions)
                    continue

                try:
                    request = _ipc_models.IPCRequest.model_validate(raw_request)
                except Exception:
                    logger.exception("ipc.invalid_request_frame", extra={"request_id": request_id})
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
                            id=request_id,
                            done=True,
                            payload=None,
                            engine_context=None,
                            error="invalid request frame",
                        ),
                    )
                    continue

                if request.action not in active_actions:
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=None,
                            engine_context=None,
                            error=(
                                f"action '{request.action}' was not negotiated for this connection"
                            ),
                        ),
                    )
                    continue

                engine_context: dict[str, Any] = {}
                try:
                    request_id_token = _ipc_models._current_ipc_request_id.set(request.id)
                    try:
                        engine_context = await self._registry.run_on_request(
                            request.action,
                            request.payload,
                            engine_context,
                        )
                    finally:
                        _ipc_models._current_ipc_request_id.reset(request_id_token)
                except BudgetKilledException as exc:
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=budget_killed_exception_to_payload(exc),
                            engine_context=engine_context,
                            error=str(exc),
                        ),
                    )
                    continue

                if request.action not in _ipc_models.RPC_ALLOWLIST:
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
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
                            _ipc_models.IPCResponseFrame(
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
                            request_id_token = _ipc_models._current_ipc_request_id.set(request.id)
                            try:
                                engine_context = await self._registry.run_on_stream_chunk(
                                    request.action,
                                    chunk,
                                    engine_context,
                                )
                            finally:
                                _ipc_models._current_ipc_request_id.reset(request_id_token)
                            await self._write_frame(
                                writer,
                                _ipc_models.IPCResponseFrame(
                                    id=request.id,
                                    done=False,
                                    payload=chunk,
                                    engine_context=engine_context,
                                    error=None,
                                ),
                            )
                        # Streaming handlers accrue/report usage via on_stream_chunk. The terminal
                        # on_response payload is intentionally empty so interceptors do not double-count.
                        request_id_token = _ipc_models._current_ipc_request_id.set(request.id)
                        try:
                            engine_context = await self._registry.run_on_response(
                                request.action,
                                {},
                                engine_context,
                            )
                        finally:
                            _ipc_models._current_ipc_request_id.reset(request_id_token)
                        await self._write_frame(
                            writer,
                            _ipc_models.IPCResponseFrame(
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

                    request_id_token = _ipc_models._current_ipc_request_id.set(request.id)
                    try:
                        engine_context = await self._registry.run_on_response(
                            request.action,
                            payload,
                            engine_context,
                        )
                    finally:
                        _ipc_models._current_ipc_request_id.reset(request_id_token)
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=payload,
                            engine_context=engine_context,
                            error=None,
                        ),
                    )
                except Exception:
                    logger.exception(
                        "ipc.handler_failed",
                        extra={"action": request.action, "request_id": request.id},
                    )
                    await self._write_frame(
                        writer,
                        _ipc_models.IPCResponseFrame(
                            id=request.id,
                            done=True,
                            payload=None,
                            engine_context=engine_context,
                            error="handler failed",
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
        self._supported_actions = [
            "llm_call",
            "tool_call",
            "http",
            "file_io",
            "delegate",
            "write_artifact",
        ]
        self._worker_version = "worker-396"
        self._active_actions: list[str] = []
        self._initial_engine_context: dict[str, Any] = {}
        self._request_lock = asyncio.Lock()

    async def connect(self) -> _ipc_models.CapabilityResponse:
        """Open a connection to the IPC socket."""
        self._reader, self._writer = await asyncio.open_unix_connection(self._socket_path)
        capability_request = _ipc_models.CapabilityRequest(
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
            response = _ipc_models.CapabilityResponse.model_validate_json(raw_response)
        except Exception as exc:
            raise ConnectionError("invalid capability response") from exc

        self._active_actions = list(response.active_actions)
        self._initial_engine_context = dict(response.engine_context)
        if response.accepted:
            os.environ.pop("RUNSIGHT_GRANT_TOKEN", None)
            self._grant_token = ""
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
            frame = _ipc_models.IPCResponseFrame.model_validate(response)
        except Exception as exc:
            raise ConnectionError("invalid response frame") from exc

        return frame.done, frame.payload, frame.error

    def _build_request_frame(self, action: str, payload: dict[str, Any]) -> _ipc_models.IPCRequest:
        return _ipc_models.IPCRequest(
            id=str(uuid.uuid4()),
            action=action,
            payload=payload,
        )

    async def _send_request_frame(self, request: _ipc_models.IPCRequest) -> None:
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
        async with self._request_lock:
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
                        budget_exc = budget_killed_exception_from_payload(frame_payload)
                        if budget_exc is not None:
                            raise budget_exc
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
        """Send an NDJSON request and yield non-final payload frames.

        IPCClient intentionally serializes the connection: the request lock is
        held until the terminal frame so concurrent streams cannot interleave
        reads on the single persistent socket.
        """
        async with self._request_lock:
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
                        budget_exc = budget_killed_exception_from_payload(frame_payload)
                        if budget_exc is not None:
                            raise budget_exc
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
