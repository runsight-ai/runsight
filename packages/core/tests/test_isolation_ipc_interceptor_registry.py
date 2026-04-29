"""ISO-002 IPC interceptor registry tests."""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from isolation_ipc_helpers import (
    _capability_response_for,
    _make_grant_token,
    _send_raw_authenticated_request_and_collect_frames,
)


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
                assert payload == {"url": "https://example.com"}
                engine_context["budget_remaining_usd"] = 12.5
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        class ObserverLikeInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                observed.append(dict(engine_context))
                engine_context["trace_id"] = "trace-393"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(BudgetLikeInterceptor())
        registry.register(ObserverLikeInterceptor())

        context = await registry.run_on_request("http", {"url": "https://example.com"}, {})
        assert observed[0] == {}
        assert observed[1] == {"budget_remaining_usd": 12.5}
        assert context == {
            "budget_remaining_usd": 12.5,
            "trace_id": "trace-393",
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


class TestIPCServerRegistryIntegration:
    """IPCServer should run registry hooks around handler execution for all frame types."""

    @pytest.mark.asyncio
    async def test_simple_handler_runs_registry_and_emits_final_engine_context(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TestInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                assert engine_context == {}
                engine_context["request_seen"] = action
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                engine_context["response_status"] = payload["status"]
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TestInterceptor())

        sock_path = tmp_path / "run393-simple.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "ok", "echo": payload["value"]}

        grant_token = _make_grant_token(block_id="run393-simple")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-simple-1",
                    "action": "simple",
                    "payload": {"value": 7},
                },
            )
            assert handler_called is True
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 7}
            assert frames[0]["engine_context"] == {
                "request_seen": "simple",
                "response_status": "ok",
            }
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_private_engine_context_interceptor_does_not_mutate_context_without_registry_register(
        self, tmp_path: Path
    ):
        """Only explicit InterceptorRegistry.register() may mutate engine_context."""
        from runsight_core.isolation import IPCServer

        sock_path = tmp_path / "run393-no-shim.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "echo": payload.get("value")}

        grant_token = _make_grant_token(block_id="run393-no-shim")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            grant_token=grant_token,
        )
        setattr(
            server,
            "_engine_context_interceptor",
            lambda *_args, **_kwargs: {"trace_id": "legacy-shim"},
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-no-shim-1",
                    "action": "simple",
                    "payload": {"value": 42},
                },
            )
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 42}
            assert frames[0]["engine_context"] == {}
            assert "trace_id" not in frames[0]["engine_context"]
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_stream_handler_runs_chunk_hook_per_chunk(self, tmp_path: Path):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        chunk_indices: list[int] = []

        class TestInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["chunk_count"] = 0
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["response_seen"] = True
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                chunk_indices.append(chunk["index"])
                engine_context["chunk_count"] += 1
                return engine_context

        registry.register(TestInterceptor())

        sock_path = tmp_path / "run393-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def stream_handler(payload: dict[str, Any]):
            yield {"index": 1, "value": "A"}
            yield {"index": 2, "value": "B"}
            yield {"index": 3, "value": "C"}

        grant_token = _make_grant_token(block_id="run393-stream")
        server = IPCServer(
            sock=server_sock,
            handlers={"stream": stream_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-stream-1",
                    "action": "stream",
                    "payload": {"topic": "demo"},
                },
                max_frames=8,
            )
            assert chunk_indices == [1, 2, 3]
            assert [frame["done"] for frame in frames] == [False, False, False, True]
            assert frames[-1]["engine_context"] == {
                "chunk_count": 3,
                "response_seen": True,
            }
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_budget_killed_in_on_request_short_circuits_handler(self, tmp_path: Path):
        from runsight_core.budget_enforcement import BudgetKilledException
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class KillSwitchInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                if action == "capability_negotiation":
                    return engine_context
                raise BudgetKilledException(
                    scope="workflow",
                    block_id=None,
                    limit_kind="cost_usd",
                    limit_value=10.0,
                    actual_value=12.0,
                )

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(KillSwitchInterceptor())

        sock_path = tmp_path / "run393-killed.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def should_not_run(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "unexpected"}

        grant_token = _make_grant_token(block_id="run393-killed")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": should_not_run},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-kill-1",
                    "action": "simple",
                    "payload": {"value": "blocked"},
                },
            )
            assert handler_called is False
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"]["error_type"] == "BudgetKilledException"
            assert frames[0]["payload"]["scope"] == "workflow"
            assert frames[0]["payload"]["limit_kind"] == "cost_usd"
            assert frames[0]["error"] is not None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_subprocess_sent_engine_context_is_rejected_and_never_reaches_registry(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        on_request_actions: list[str] = []

        class SpyInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                on_request_actions.append(action)
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(SpyInterceptor())

        sock_path = tmp_path / "run393-tamper.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok"}

        grant_token = _make_grant_token(block_id="run393-tamper")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": simple_handler},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-393-tamper-1",
                    "action": "simple",
                    "payload": {"value": 1},
                    "engine_context": {"subprocess_injected": True},
                },
            )
            assert on_request_actions == ["capability_negotiation"]
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"] is None
            assert "invalid request frame" in (frames[0]["error"] or "")
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_request_stream_yields_only_non_final_payloads(self, tmp_path: Path):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "run392-client-stream.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)

        async def fake_stream_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                assert raw_capability
                capability_request = json.loads(raw_capability)
                capability_response = (
                    json.dumps(
                        _capability_response_for(capability_request, active_actions=["delegate"])
                    )
                    + "\n"
                )
                writer.write(capability_response.encode())
                await writer.drain()

                raw_request = await reader.readline()
                assert raw_request
                for frame in [
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "A"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "B"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": False,
                        "payload": {"chunk": "C"},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": True,
                        "payload": {"final": True},
                        "engine_context": {"trace_id": "s1"},
                        "error": None,
                    },
                ]:
                    writer.write((json.dumps(frame) + "\n").encode())
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server_task = asyncio.create_task(fake_stream_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            await client.connect()
            chunks = []
            async for payload in client.request_stream("delegate", {"task": "demo"}):
                chunks.append(payload)
            assert chunks == [{"chunk": "A"}, {"chunk": "B"}, {"chunk": "C"}]
        finally:
            await client.close()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)
