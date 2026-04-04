"""IPC server and client using Unix sockets with NDJSON framing (ISO-002)."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from typing import Any, Awaitable, Callable

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

BLOCKED_ACTIONS = frozenset({"llm_call"})


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
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue

                request_id = request.get("id", "")
                action = request.get("action", "")

                if action in BLOCKED_ACTIONS or action not in self._handlers:
                    response = {"id": request_id, "error": f"unsupported action: {action}"}
                else:
                    handler = self._handlers[action]
                    # Build params dict: everything except 'id' and 'action'
                    params = {k: v for k, v in request.items() if k not in ("id", "action")}
                    try:
                        result = await handler(params)
                        response = {"id": request_id, **result}
                    except Exception as exc:
                        response = {"id": request_id, "error": str(exc)}

                response_line = json.dumps(response, separators=(",", ":")) + "\n"
                writer.write(response_line.encode())
                await writer.drain()
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

    async def request(self, action: str, **params: Any) -> dict[str, Any]:
        """Send an NDJSON request and return the response with matching id."""
        if self._closed:
            raise ConnectionError("IPC client is closed")

        if self._writer is None or self._reader is None:
            await self.connect()

        request_id = str(uuid.uuid4())
        msg = {"id": request_id, "action": action, **params}
        line = json.dumps(msg, separators=(",", ":")) + "\n"

        try:
            self._writer.write(line.encode())
            await self._writer.drain()

            response_line = await self._reader.readline()
            if not response_line:
                self._closed = True
                raise ConnectionError("IPC socket disconnected")

            response = json.loads(response_line)
            # Strip the correlation id before returning
            response.pop("id", None)
            return response
        except (ConnectionResetError, BrokenPipeError) as exc:
            self._closed = True
            raise ConnectionError("IPC socket disconnected") from exc

    async def close(self) -> None:
        """Close the connection."""
        self._closed = True
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._reader = None
