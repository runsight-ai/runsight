"""Smoke coverage for IPC process-boundary budget wiring."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from isolation_ipc_helpers import _make_budget_interceptor, _make_grant_token

pytestmark = pytest.mark.real_subprocess_isolation


@pytest.mark.asyncio
async def test_budget_interceptor_accrues_over_ipc_and_kills_next_request(tmp_path: Path) -> None:
    """IPCServer, auth handshake, budget interceptor, and handler dispatch work together."""
    from runsight_core.budget_enforcement import BudgetSession
    from runsight_core.isolation import IPCServer
    from runsight_core.isolation import interceptors as interceptors_module

    registry = interceptors_module.InterceptorRegistry()
    budget_session = BudgetSession(
        scope_name="block:process-budget-smoke",
        cost_cap_usd=0.01,
        token_cap=100,
        on_exceed="fail",
    )
    registry.register(
        _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="process-budget-smoke",
        )
    )
    handler_calls: list[dict[str, Any]] = []

    async def llm_handler(payload: dict[str, Any]) -> dict[str, Any]:
        handler_calls.append(payload)
        return {"content": "ok", "cost_usd": 0.05, "total_tokens": 7}

    sock_path = tmp_path / "process-budget-smoke.sock"
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(str(sock_path))
    server_sock.listen(1)
    grant_token = _make_grant_token(block_id="process-budget-smoke")
    server = IPCServer(
        sock=server_sock,
        handlers={"llm_call": llm_handler},
        registry=registry,
        grant_token=grant_token,
    )
    server_task = asyncio.create_task(server.serve())

    async def send(
        writer: asyncio.StreamWriter,
        reader: asyncio.StreamReader,
        request_id: str,
    ) -> dict[str, Any]:
        writer.write(
            (
                json.dumps(
                    {
                        "id": request_id,
                        "action": "llm_call",
                        "payload": {
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": request_id}],
                        },
                    },
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
        )
        await writer.drain()
        return json.loads(await reader.readline())

    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.open_unix_connection(str(sock_path))
        writer.write(
            (
                json.dumps(
                    {
                        "id": "capability",
                        "action": "capability_negotiation",
                        "grant_token": grant_token.token,
                        "supported_actions": ["llm_call"],
                        "worker_version": "process-worker",
                    },
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
        )
        await writer.drain()
        assert json.loads(await reader.readline())["accepted"] is True

        first = await send(writer, reader, "request-1")
        second = await send(writer, reader, "request-2")

        assert first["payload"] == {"content": "ok", "cost_usd": 0.05, "total_tokens": 7}
        assert first["engine_context"]["budget_remaining_usd"] == pytest.approx(-0.04)
        assert second["payload"]["error_type"] == "BudgetKilledException"
        assert second["payload"]["block_id"] == "process-budget-smoke"
        assert len(handler_calls) == 1
        assert budget_session.cost_usd == pytest.approx(0.05)
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        await server.shutdown()
        server_task.cancel()
        server_sock.close()
        sock_path.unlink(missing_ok=True)
