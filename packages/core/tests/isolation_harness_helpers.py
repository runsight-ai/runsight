"""Package-local helpers for workspace isolation tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from runsight_core.isolation import ContextEnvelope, PromptEnvelope, ResultEnvelope, SoulEnvelope


def _fixture_url(path: str = "/v1") -> str:
    return "https" + "://" + "network-override.fixture.test" + path


def _socket_fixture_path(tmp_path: Path, filename: str) -> str:
    return str(tmp_path / filename)


class _RecordingStdIn:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


class _StaticStdOut:
    def __init__(self, result: ResultEnvelope) -> None:
        self._result = result
        self._sent = False

    async def read(self, n: int = -1) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        payload = self._result.model_dump_json().encode()
        if n is None or n < 0:
            return payload
        return payload[:n]


class _HangingStdOut:
    async def read(self, n: int = -1) -> bytes:
        del n
        await asyncio.Event().wait()
        return b""


class _EmptyStdErr:
    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        return b""


class _FakeRunProcess:
    def __init__(self, result: ResultEnvelope) -> None:
        self.stdin = _RecordingStdIn()
        self.stdout = _StaticStdOut(result)
        self.stderr = _EmptyStdErr()
        self.returncode = 0
        self.pid = 4242

    async def wait(self) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class _FakeHangingProcess(_FakeRunProcess):
    def __init__(self) -> None:
        super().__init__(_make_result_envelope())
        self.stdout = _HangingStdOut()
        self.returncode = None


class _NoopIPCServer:
    def __init__(self, **_kwargs: Any) -> None:
        return None

    async def serve(self) -> None:
        await asyncio.sleep(0)

    async def shutdown(self) -> None:
        return None


def _patch_harness_subprocess_result(
    monkeypatch: pytest.MonkeyPatch,
    harness_module: Any,
    result: ResultEnvelope,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    proc = _FakeRunProcess(result)

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> _FakeRunProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        captured["proc"] = proc
        return proc

    monkeypatch.setattr(
        harness_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    return captured


def _patch_harness_run_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    harness_module: Any,
    result: ResultEnvelope,
) -> dict[str, Any]:
    captured = _patch_harness_subprocess_result(monkeypatch, harness_module, result)
    monkeypatch.setattr(harness_module, "IPCServer", _NoopIPCServer)
    return captured


def _patch_harness_hanging_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    harness_module: Any,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    proc = _FakeHangingProcess()

    async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> _FakeHangingProcess:
        captured["args"] = args
        captured["kwargs"] = kwargs
        captured["proc"] = proc
        return proc

    monkeypatch.setattr(harness_module, "IPCServer", _NoopIPCServer)
    monkeypatch.setattr(
        harness_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    return captured


def _make_soul_envelope() -> SoulEnvelope:
    return SoulEnvelope(
        id="harness-soul",
        role="Tester",
        system_prompt="You test things.",
        model_name="gpt-4o-mini",
        max_tool_iterations=3,
    )


def _make_context_envelope(
    *,
    block_id: str = "harness-block",
    block_type: str = "linear",
    scoped_results: dict[str, Any] | None = None,
    scoped_shared_memory: dict[str, Any] | None = None,
    timeout_seconds: int = 30,
    max_output_bytes: int = 1_000_000,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config={},
        soul=_make_soul_envelope(),
        tools=[],
        prompt=PromptEnvelope(id="harness-prompt", instruction="Do the thing.", context={}),
        scoped_results=scoped_results or {},
        scoped_shared_memory=scoped_shared_memory or {},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def _make_result_envelope(
    *,
    block_id: str = "harness-block",
    output: str = "done",
    error: str | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(
        block_id=block_id,
        output=output,
        exit_handle="done",
        cost_usd=0.0,
        total_tokens=0,
        tool_calls_made=0,
        delegate_artifacts={},
        conversation_history=[],
        error=error,
        error_type=None,
    )


async def _tool_call_passthrough(args: dict[str, Any]) -> str:
    return f"ok:{args['value']}"
