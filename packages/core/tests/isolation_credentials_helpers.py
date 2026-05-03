"""Shared helpers for isolation credential owner suites."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any

from runsight_core.isolation import (
    ContextEnvelope,
    IPCClient,
    IPCServer,
    PromptEnvelope,
    SoulEnvelope,
)


def _make_context_envelope(
    *,
    block_id: str = "credential-linear-block",
    block_type: str = "linear",
    block_config: dict[str, Any] | None = None,
    tools: list | None = None,
    timeout_seconds: int = 30,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config=block_config or {},
        soul=SoulEnvelope(
            id="credential-soul",
            role="Tester",
            system_prompt="You test things.",
            model_name="fixture-model",
            max_tool_iterations=3,
        ),
        tools=tools or [],
        prompt=PromptEnvelope(id="credential-prompt", instruction="Do the thing.", context={}),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=1_000_000,
    )


async def _setup_ipc_pair(
    tmp_path: Path,
    handlers: dict[str, Any],
    *,
    sock_name: str = "test.sock",
) -> tuple[IPCServer, IPCClient, socket.socket, Path, asyncio.Task]:
    """Create an IPC server+client pair for testing handlers."""
    sock_path = tmp_path / sock_name
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(str(sock_path))
    server_sock.listen(1)

    server = IPCServer(sock=server_sock, handlers=handlers)
    server_task = asyncio.create_task(server.serve())

    client = IPCClient(socket_path=str(sock_path))
    await client.connect()

    return server, client, server_sock, sock_path, server_task


async def _teardown_ipc_pair(
    server: IPCServer,
    client: IPCClient,
    server_sock: socket.socket,
    sock_path: Path,
    server_task: asyncio.Task,
) -> None:
    """Clean up an IPC server+client pair."""
    await client.close()
    await server.shutdown()
    server_task.cancel()
    server_sock.close()
    sock_path.unlink(missing_ok=True)


async def _tool_call_echo(args: dict[str, Any]) -> str:
    return f"echo:{args['value']}"


async def _tool_call_boom(args: dict[str, Any]) -> str:
    raise RuntimeError("boom")
