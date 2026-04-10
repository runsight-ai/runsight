"""IPC server and client using Unix sockets with NDJSON framing (ISO-002)."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

HandlerResult = Awaitable[dict[str, Any]] | AsyncIterable[dict[str, Any]]
Handler = Callable[[dict[str, Any]], HandlerResult]

BLOCKED_ACTIONS = frozenset({"llm_call"})


class IPCRequest(BaseModel):
    """Request envelope sent from engine process to worker process."""

    model_config = ConfigDict(extra="forbid")

    id: str
    action: str
    payload: dict[str, Any]


class IPCResponseFrame(BaseModel):
    """Streamed response frame sent from worker process to engine process."""

    id: str
    done: bool
    payload: Any | None
    engine_context: dict[str, Any] | None
    error: str | None


def _is_async_iterable(value: Any) -> bool:
    return hasattr(value, "__aiter__")


class IPCServer:
    """Async Unix socket server that dispatches NDJSON requests to handlers.

    Accepts an already-bound socket object (does not create or bind one).
    """

    def __init__(self, *, sock: socket.socket, handlers: dict[str, Handler]) -> None:
        if not isinstance(sock, socket.socket):
            raise TypeError("sock must be a socket.socket instance, not a path string")
        self._sock = sock
        self._handlers = handlers
        self._server: asyncio.AbstractServer | None = None
        self._shutdown_event = asyncio.Event()
        # Capture the socket path for cleanup
        try:
            self._sock_path: str | None = sock.getsockname()
        except OSError:
            self._sock_path = None

    def _build_engine_context(self, request: IPCRequest) -> dict[str, Any] | None:
        interceptor = getattr(self, "_engine_context_interceptor", None)
        if not callable(interceptor):
            return None
        try:
            value = interceptor(request)
        except TypeError:
            value = interceptor()
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    async def _write_frame(self, writer: asyncio.StreamWriter, frame: IPCResponseFrame) -> None:
        line = json.dumps(frame.model_dump(), separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

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

                engine_context = self._build_engine_context(request)

                if request.action in BLOCKED_ACTIONS or request.action not in self._handlers:
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

                handler = self._handlers[request.action]
                try:
                    result_or_stream = handler(request.payload)
                    if _is_async_iterable(result_or_stream):
                        async for chunk in result_or_stream:
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

    async def connect(self) -> None:
        """Open a connection to the IPC socket."""
        self._reader, self._writer = await asyncio.open_unix_connection(self._socket_path)

    def _build_request_payload(
        self, payload: dict[str, Any] | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        if payload is None:
            return dict(params)
        merged = dict(payload)
        merged.update(params)
        return merged

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

    def _build_request_frame(
        self,
        action: str,
        payload: dict[str, Any] | None,
        params: dict[str, Any],
    ) -> IPCRequest:
        request_payload = self._build_request_payload(payload, params)
        return IPCRequest(
            id=str(uuid.uuid4()),
            action=action,
            payload=request_payload,
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
        payload: dict[str, Any] | None = None,
        **params: Any,
    ) -> Any:
        """Send an NDJSON request and return the final payload frame."""
        if self._closed:
            raise ConnectionError("IPC client is closed")

        if self._writer is None or self._reader is None:
            await self.connect()

        request = self._build_request_frame(action, payload, params)

        try:
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
        payload: dict[str, Any] | None = None,
        **params: Any,
    ):
        """Send an NDJSON request and yield non-final payload frames."""
        if self._closed:
            raise ConnectionError("IPC client is closed")

        if self._writer is None or self._reader is None:
            await self.connect()

        request = self._build_request_frame(action, payload, params)

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
