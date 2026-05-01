"""IPC process-boundary integration tests."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from isolation_ipc_helpers import (
    _make_budget_interceptor,
    _make_grant_token,
    _send_raw_authenticated_request_and_collect_frames,
)


class TestProcessBoundaryIntegration:
    """IPCServer, IPCClient, handlers, auth, and interceptors work together."""

    @pytest.mark.asyncio
    async def test_llm_call_flows_through_budget_interceptor_and_returns_engine_context(
        self, tmp_path: Path
    ):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        registry = interceptors_module.InterceptorRegistry()
        budget_session = BudgetSession(
            scope_name="block:process-llm-block",
            cost_cap_usd=0.50,
            token_cap=100,
            on_exceed="fail",
        )
        registry.register(
            _make_budget_interceptor(
                interceptors_module,
                session=budget_session,
                block_id="process-llm-block",
            )
        )

        async def llm_handler(payload: dict[str, Any]) -> dict[str, Any]:
            assert payload["model"] == "gpt-4o-mini"
            return {"content": "ok", "cost_usd": 0.05, "total_tokens": 7}

        sock_path = tmp_path / "process-llm-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        grant_token = _make_grant_token(block_id="process-llm-block")
        server = IPCServer(
            sock=server_sock,
            handlers={"llm_call": llm_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-process-llm-block",
                    "action": "llm_call",
                    "payload": {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                },
            )
            assert frames == [
                {
                    "id": "req-process-llm-block",
                    "done": True,
                    "payload": {"content": "ok", "cost_usd": 0.05, "total_tokens": 7},
                    "engine_context": {
                        "budget_remaining_usd": pytest.approx(0.45),
                        "budget_remaining_tokens": 93,
                    },
                    "error": None,
                }
            ]
            assert budget_session.cost_usd == pytest.approx(0.05)
            assert budget_session.tokens == 7
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_over_cap_response_accrues_then_next_request_is_killed_on_request(
        self, tmp_path: Path
    ):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        registry = interceptors_module.InterceptorRegistry()
        budget_session = BudgetSession(
            scope_name="block:process-budget-cap-block",
            cost_cap_usd=0.01,
            token_cap=100,
            on_exceed="fail",
        )
        registry.register(
            _make_budget_interceptor(
                interceptors_module,
                session=budget_session,
                block_id="process-budget-cap-block",
            )
        )

        handler_calls: list[dict[str, Any]] = []

        async def llm_handler(payload: dict[str, Any]) -> dict[str, Any]:
            handler_calls.append(payload)
            return {
                "content": f"ok-{len(handler_calls)}",
                "cost_usd": 0.05,
                "total_tokens": 7,
            }

        sock_path = tmp_path / "process-budget-cap-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        grant_token = _make_grant_token(block_id="process-budget-cap-block")
        server = IPCServer(
            sock=server_sock,
            handlers={"llm_call": llm_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        async def send_request(
            writer: asyncio.StreamWriter,
            reader: asyncio.StreamReader,
            *,
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

        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_unix_connection(str(sock_path))
            writer.write(
                (
                    json.dumps(
                        {
                            "id": "process-budget-capability",
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
            capability = json.loads(await reader.readline())
            assert capability["accepted"] is True

            first = await send_request(writer, reader, request_id="process-budget-request-1")
            assert first["done"] is True
            assert first["error"] is None
            assert first["payload"] == {
                "content": "ok-1",
                "cost_usd": 0.05,
                "total_tokens": 7,
            }
            assert first["engine_context"]["budget_remaining_usd"] == pytest.approx(-0.04)
            assert budget_session.cost_usd == pytest.approx(0.05)
            assert len(handler_calls) == 1

            second = await send_request(writer, reader, request_id="process-budget-request-2")
            assert second["id"] == "process-budget-request-2"
            assert second["done"] is True
            assert second["payload"]["error_type"] == "BudgetKilledException"
            assert second["payload"]["block_id"] == "process-budget-cap-block"
            assert second["payload"]["actual_value"] == pytest.approx(0.05)
            assert "budget" in (second["error"] or "").lower()
            assert len(handler_calls) == 1
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_grant_token_accepts_first_connection_and_rejects_second(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer

        async def llm_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"content": "ok"}

        sock_path = tmp_path / "process-auth-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        grant_token = _make_grant_token(block_id="process-auth-block")
        server = IPCServer(
            sock=server_sock,
            handlers={"llm_call": llm_handler},
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        async def authenticate() -> dict[str, Any]:
            reader, writer = await asyncio.open_unix_connection(str(sock_path))
            try:
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": "cap-process-auth-block",
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
                return json.loads(await reader.readline())
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            first = await authenticate()
            second = await authenticate()

            assert first["accepted"] is True
            assert "llm_call" in first["active_actions"]
            assert second["accepted"] is False
            assert "rejected" in (second["error"] or "")
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_all_core_handlers_dispatch_through_same_interceptor_chain(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        registry = interceptors_module.InterceptorRegistry()
        calls: list[tuple[str, str]] = []

        class RecordingInterceptor:
            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                if action != "capability_negotiation":
                    calls.append(("request", action))
                    engine_context["request_action"] = action
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                if action != "capability_negotiation":
                    calls.append(("response", action))
                    engine_context["response_action"] = action
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

        registry.register(RecordingInterceptor())

        async def llm_call(payload: dict[str, Any]) -> dict[str, Any]:
            return {"kind": "llm", "content": payload["prompt"]}

        async def tool_call(payload: dict[str, Any]) -> dict[str, Any]:
            return {"kind": "tool", "output": payload["name"]}

        async def http(payload: dict[str, Any]) -> dict[str, Any]:
            return {"kind": "http", "status_code": 200, "url": payload["url"]}

        async def file_io(payload: dict[str, Any]) -> dict[str, Any]:
            return {"kind": "file_io", "path": payload["path"]}

        sock_path = tmp_path / "process-all-handlers-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        grant_token = _make_grant_token(block_id="process-all-handlers-block")
        server = IPCServer(
            sock=server_sock,
            handlers={
                "llm_call": llm_call,
                "tool_call": tool_call,
                "http": http,
                "file_io": file_io,
            },
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        async def send(
            writer: asyncio.StreamWriter,
            reader: asyncio.StreamReader,
            *,
            request_id: str,
            action: str,
            payload: dict[str, Any],
        ) -> dict[str, Any]:
            writer.write(
                (
                    json.dumps(
                        {"id": request_id, "action": action, "payload": payload},
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            await writer.drain()
            return json.loads(await reader.readline())

        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_unix_connection(str(sock_path))
            writer.write(
                (
                    json.dumps(
                        {
                            "id": "process-all-handlers-capability",
                            "action": "capability_negotiation",
                            "grant_token": grant_token.token,
                            "supported_actions": ["llm_call", "tool_call", "http", "file_io"],
                            "worker_version": "process-worker",
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            await writer.drain()
            capability = json.loads(await reader.readline())
            assert capability["accepted"] is True

            responses = [
                await send(
                    writer,
                    reader,
                    request_id="req-process-llm-block",
                    action="llm_call",
                    payload={"prompt": "hello"},
                ),
                await send(
                    writer,
                    reader,
                    request_id="process-tool-request",
                    action="tool_call",
                    payload={"name": "echo"},
                ),
                await send(
                    writer,
                    reader,
                    request_id="process-http-request",
                    action="http",
                    payload={"url": "https://api.fixture.test/data"},
                ),
                await send(
                    writer,
                    reader,
                    request_id="process-file-request",
                    action="file_io",
                    payload={"path": "notes/out.txt"},
                ),
            ]

            assert [response["payload"]["kind"] for response in responses] == [
                "llm",
                "tool",
                "http",
                "file_io",
            ]
            assert [response["engine_context"]["request_action"] for response in responses] == [
                "llm_call",
                "tool_call",
                "http",
                "file_io",
            ]
            assert calls == [
                ("request", "llm_call"),
                ("response", "llm_call"),
                ("request", "tool_call"),
                ("response", "tool_call"),
                ("request", "http"),
                ("response", "http"),
                ("request", "file_io"),
                ("response", "file_io"),
            ]
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_streaming_llm_call_round_trip_yields_chunks_and_runs_chunk_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from runsight_core.isolation import IPCClient, IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        registry = interceptors_module.InterceptorRegistry()
        chunk_contents: list[str] = []

        class StreamInterceptor:
            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                engine_context["chunk_count"] = 0
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                engine_context["final_seen"] = True
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                assert action == "llm_call"
                chunk_contents.append(chunk["content"])
                engine_context["chunk_count"] += 1
                return engine_context

        registry.register(StreamInterceptor())

        async def stream_llm(_payload: dict[str, Any]):
            yield {"content": "one", "tokens": 1, "cost_usd": 0.0}
            yield {"content": "two", "tokens": 1, "cost_usd": 0.0}
            yield {"content": "three", "tokens": 1, "cost_usd": 0.0}

        sock_path = tmp_path / "process-stream-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        grant_token = _make_grant_token(block_id="process-stream-block")
        server = IPCServer(
            sock=server_sock,
            handlers={"llm_call": stream_llm},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())
        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", grant_token.token)
        client = IPCClient(socket_path=str(sock_path))

        try:
            capability = await client.connect()
            assert capability.accepted is True

            chunks: list[dict[str, Any]] = []
            async for chunk in client.request_stream(
                "llm_call",
                {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            ):
                chunks.append(chunk)

            assert [chunk["content"] for chunk in chunks] == ["one", "two", "three"]
            assert chunk_contents == ["one", "two", "three"]
        finally:
            await client.close()
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)
