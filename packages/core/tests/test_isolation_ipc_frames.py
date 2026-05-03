"""IPC frame model and streaming response tests."""

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

pytestmark = pytest.mark.real_subprocess_isolation

# ---------------------------------------------------------------------------
# IPCFrame protocol and NDJSON streaming
# ---------------------------------------------------------------------------


class TestIPCFrameModels:
    """Typed request/response frame models define the IPC contract."""

    def test_ipc_request_has_id_action_payload_and_forbids_engine_context(self):
        from pydantic import ValidationError
        from runsight_core.isolation.ipc_models import IPCRequest

        assert set(IPCRequest.model_fields) == {"id", "action", "payload"}

        req = IPCRequest(id="req-1", action="http", payload={"url": "https://fixture.test"})
        assert req.id == "req-1"
        assert req.action == "http"
        assert req.payload == {"url": "https://fixture.test"}

        with pytest.raises(ValidationError):
            IPCRequest(
                id="req-2",
                action="http",
                payload={"url": "https://fixture.test"},
                engine_context={"trace_id": "forbidden"},
            )

    def test_ipc_response_frame_has_complete_contract(self):
        from runsight_core.isolation.ipc_models import IPCResponseFrame

        assert set(IPCResponseFrame.model_fields) == {
            "id",
            "done",
            "payload",
            "engine_context",
            "error",
        }

        frame = IPCResponseFrame(
            id="req-1",
            done=False,
            payload={"chunk": "A"},
            engine_context={"trace_id": "t-1"},
            error=None,
        )
        assert frame.done is False
        assert frame.payload == {"chunk": "A"}
        assert frame.engine_context == {"trace_id": "t-1"}
        assert frame.error is None


class TestServerStreamingFrames:
    """IPCServer must emit response frames for both simple and streaming handlers."""

    @pytest.mark.asyncio
    async def test_simple_handler_returns_single_done_frame_with_engine_context(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TraceInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["trace_id"] = "trace-simple-1"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TraceInterceptor())

        sock_path = tmp_path / "simple-frame-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def simple_handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "ok", "echo": payload.get("value")}

        grant_token = _make_grant_token(block_id="simple-frame-block")
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
                    "id": "req-simple-1",
                    "action": "simple",
                    "payload": {"value": 123},
                },
            )
            assert len(frames) == 1
            assert frames[0]["id"] == "req-simple-1"
            assert frames[0]["done"] is True
            assert frames[0]["payload"] == {"status": "ok", "echo": 123}
            assert frames[0]["engine_context"] == {"trace_id": "trace-simple-1"}
            assert frames[0]["error"] is None
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_stream_handler_returns_three_non_final_frames_and_one_final(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        class TraceInterceptor:
            async def on_request(self, action: str, payload: dict, engine_context: dict) -> dict:
                engine_context["trace_id"] = "trace-stream-1"
                return engine_context

            async def on_response(self, action: str, payload: dict, engine_context: dict) -> dict:
                return engine_context

            async def on_stream_chunk(self, action: str, chunk: dict, engine_context: dict) -> dict:
                return engine_context

        registry.register(TraceInterceptor())

        sock_path = tmp_path / "stream-frame-block.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        async def stream_handler(payload: dict[str, Any]):
            assert payload == {"topic": "demo"}
            yield {"chunk": 1}
            yield {"chunk": 2}
            yield {"chunk": 3}

        grant_token = _make_grant_token(block_id="stream-frame-block")
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
                    "id": "req-stream-1",
                    "action": "stream",
                    "payload": {"topic": "demo"},
                },
                max_frames=8,
            )
            assert len(frames) == 4
            assert [frame["done"] for frame in frames] == [False, False, False, True]
            assert [frame["payload"] for frame in frames[:-1]] == [
                {"chunk": 1},
                {"chunk": 2},
                {"chunk": 3},
            ]
            assert frames[-1]["payload"] is None
            assert all(
                frame["engine_context"] == {"trace_id": "trace-stream-1"} for frame in frames
            )
            assert all(frame["error"] is None for frame in frames)
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


class TestIPCClientFrameConsumption:
    """IPCClient must consume streamed frames through request/request_stream APIs."""

    def test_request_signature_has_no_legacy_var_keyword_params(self):
        """Public API is frame-first: request(action, payload) without flattened kwargs."""
        import inspect

        from runsight_core.isolation import IPCClient

        params = inspect.signature(IPCClient.request).parameters.values()
        assert all(param.kind is not inspect.Parameter.VAR_KEYWORD for param in params)

    @pytest.mark.asyncio
    async def test_request_writes_capability_and_request_as_single_ndjson_lines(
        self, tmp_path: Path
    ):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "client-ndjson-lines.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)
        server_sock.setblocking(False)
        received_lines: list[bytes] = []

        async def fake_server() -> None:
            loop = asyncio.get_running_loop()
            conn, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio.open_connection(sock=conn)
            try:
                raw_capability = await reader.readline()
                received_lines.append(raw_capability)
                capability_request = json.loads(raw_capability)
                writer.write(
                    (
                        json.dumps(
                            _capability_response_for(
                                capability_request,
                                active_actions=["file_io"],
                            )
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()

                raw_request = await reader.readline()
                received_lines.append(raw_request)
                request = json.loads(raw_request)
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": request["id"],
                                "done": True,
                                "payload": {"ok": True},
                                "engine_context": None,
                                "error": None,
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server_task = asyncio.create_task(fake_server())
        client = IPCClient(socket_path=str(sock_path))
        try:
            result = await client.request(
                "file_io",
                {
                    "action_type": "write",
                    "path": "/tmp/test.txt",
                    "content": "line1\nline2\nline3",
                },
            )
            assert result == {"ok": True}
        finally:
            await client.close()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)

        assert len(received_lines) == 2
        assert all(line.endswith(b"\n") for line in received_lines)
        assert all(b"\n" not in line[:-1] for line in received_lines)
        handshake = json.loads(received_lines[0])
        request = json.loads(received_lines[1])
        assert handshake["action"] == "capability_negotiation"
        assert set(request) == {"id", "action", "payload"}
        assert request["action"] == "file_io"
        assert request["payload"]["content"] == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_request_returns_payload_from_final_done_frame(self, tmp_path: Path):
        from runsight_core.isolation import IPCClient

        sock_path = tmp_path / "client-final-frame.sock"
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
                        _capability_response_for(capability_request, active_actions=["http"])
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
                        "payload": {"chunk": 1},
                        "engine_context": {"trace_id": "c1"},
                        "error": None,
                    },
                    {
                        "id": "ignored",
                        "done": True,
                        "payload": {"final": "result"},
                        "engine_context": {"trace_id": "c1"},
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
            result = await client.request("http", {"url": "https://fixture.test"})
            assert result == {"final": "result"}
        finally:
            await client.close()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)
