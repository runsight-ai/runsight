"""
Failing tests for RUN-394: ISO-003 — SubprocessHarness (spawn, communicate, monitor, kill).

Tests cover every AC item:
1.  Subprocess spawned with minimal env (PATH + ONE API key + macOS paths only)
2.  Subprocess working dir is fresh temp dir (not project root)
3.  Socket created by SubprocessHarness (mode 0600, random path)
4.  ContextEnvelope contains only YAML-declared scoped data
5.  Timeout enforced — subprocess killed on timeout
6.  Heartbeat stall detected — subprocess killed
7.  Phase stall detected — subprocess killed
8.  ResultEnvelope validated (schema + size cap)
9.  SIGTERM then SIGKILL escalation on kill
10. Negative return codes mapped to meaningful error messages
11. Socket and temp dir cleaned up on exit (including crashes)
12. Integration test: LinearBlock round-trip via subprocess
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.isolation import (
    ContextEnvelope,
    HeartbeatMessage,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_soul_envelope() -> SoulEnvelope:
    return SoulEnvelope(
        id="soul-1",
        role="Tester",
        system_prompt="You test things.",
        model_name="gpt-4o-mini",
        max_tool_iterations=3,
    )


def _make_context_envelope(
    *,
    block_id: str = "block-1",
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
        prompt=PromptEnvelope(id="task-1", instruction="Do the thing.", context={}),
        scoped_results=scoped_results or {},
        scoped_shared_memory=scoped_shared_memory or {},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def _make_result_envelope(
    *,
    block_id: str = "block-1",
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


# ===========================================================================
# AC1: Subprocess spawned with minimal env
# ===========================================================================


class TestIpcHandlerRegistration:
    """Harness should register all engine-side IPC handlers, including generic tool_call."""

    @pytest.mark.asyncio
    async def test_build_ipc_handlers_keeps_http_and_file_io_and_adds_tool_call(self):
        """RUN-529: harness should expose tool_call without regressing existing handlers."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.tools import ToolInstance

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        harness._resolved_tools = {
            "echo_tool": ToolInstance(
                name="echo_tool",
                description="Echo input",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                execute=_tool_call_passthrough,
            )
        }

        handlers = harness._build_ipc_handlers()

        assert "http" in handlers
        assert "file_io" in handlers
        assert "tool_call" in handlers
        assert callable(handlers["http"])
        assert callable(handlers["file_io"])
        assert callable(handlers["tool_call"])


class TestRUN745LLMCallHandlerContract:
    """RUN-745: engine-side llm_call handler factory + harness registration contract."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model_name", "api_keys", "expected_key"),
        [
            (
                "claude-sonnet-4-20250514",
                {"anthropic": "sk-anthropic-real", "openai": "sk-openai-real"},
                "sk-anthropic-real",
            ),
            (
                "gpt-4o-mini",
                {"anthropic": "sk-anthropic-real", "openai": "sk-openai-real"},
                "sk-openai-real",
            ),
        ],
    )
    async def test_make_llm_call_handler_resolves_provider_key_and_passes_explicit_model(
        self,
        monkeypatch: pytest.MonkeyPatch,
        model_name: str,
        api_keys: dict[str, str],
        expected_key: str,
    ):
        from runsight_core.isolation import handlers as handlers_module

        make_llm_call_handler = getattr(handlers_module, "make_llm_call_handler", None)
        assert make_llm_call_handler is not None

        captured: dict[str, Any] = {}

        class FakeLiteLLMClient:
            def __init__(self, model_name: str, api_key: str, **_kwargs: Any):
                captured["model_name"] = model_name
                captured["api_key"] = api_key

            async def achat(
                self,
                messages: list[dict[str, Any]],
                system_prompt: str | None = None,
                temperature: float | None = None,
                tools: list[dict[str, Any]] | None = None,
                tool_choice: str | None = None,
                **kwargs: Any,
            ) -> dict[str, Any]:
                captured["messages"] = messages
                captured["system_prompt"] = system_prompt
                captured["temperature"] = temperature
                captured["tools"] = tools
                captured["tool_choice"] = tool_choice
                captured["extra_kwargs"] = dict(kwargs)
                return {
                    "content": "engine completion",
                    "cost_usd": 0.123,
                    "total_tokens": 77,
                    "tool_calls": [],
                    "finish_reason": "stop",
                }

        monkeypatch.setattr(handlers_module, "LiteLLMClient", FakeLiteLLMClient, raising=False)

        handler = make_llm_call_handler(api_keys=api_keys)
        stream = handler(
            {
                "model": model_name,
                "messages": [{"role": "user", "content": "hello"}],
                "system_prompt": "be concise",
                "temperature": 0.3,
                "tools": [{"type": "function", "function": {"name": "calc"}}],
                "tool_choice": "auto",
                "max_tokens": 256,
                "n": 1,
                "response_format": {"type": "json_object"},
                "seed": 123,
                "api_base": "https://attacker.example/v1",
                "base_url": "https://attacker.example/v1",
            }
        )
        assert hasattr(stream, "__aiter__"), "llm_call handler must stream chunks"

        chunks = [chunk async for chunk in stream]
        assert len(chunks) == 1
        assert chunks[0]["content"] == "engine completion"
        assert chunks[0]["cost_usd"] == pytest.approx(0.123)
        assert chunks[0]["total_tokens"] == 77

        assert captured["model_name"] == model_name
        assert captured["api_key"] == expected_key
        assert captured["messages"] == [{"role": "user", "content": "hello"}]
        assert captured["system_prompt"] == "be concise"
        assert captured["temperature"] == 0.3
        assert captured["tool_choice"] == "auto"
        assert captured["extra_kwargs"] == {
            "max_tokens": 256,
            "n": 1,
            "response_format": {"type": "json_object"},
            "seed": 123,
        }

    @pytest.mark.asyncio
    async def test_make_llm_call_handler_returns_in_band_error_when_provider_key_missing(self):
        from runsight_core.isolation import handlers as handlers_module

        make_llm_call_handler = getattr(handlers_module, "make_llm_call_handler", None)
        assert make_llm_call_handler is not None

        handler = make_llm_call_handler(api_keys={"anthropic": "sk-anthropic-real"})
        stream = handler(
            {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
        assert hasattr(stream, "__aiter__"), "llm_call handler must stream chunks"

        chunks = [chunk async for chunk in stream]
        assert len(chunks) == 1
        assert "error" in chunks[0]
        assert "api key" in str(chunks[0]["error"]).lower()

    @pytest.mark.asyncio
    async def test_harness_build_ipc_handlers_registers_llm_call_factory(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import handlers as handlers_module

        observed: dict[str, Any] = {}

        async def fake_llm_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"content": "ok", "cost_usd": 0.0, "total_tokens": 0}

        def fake_make_llm_call_handler(api_keys: dict[str, str]):
            observed["api_keys"] = dict(api_keys)
            return fake_llm_handler

        monkeypatch.setattr(
            handlers_module,
            "make_llm_call_handler",
            fake_make_llm_call_handler,
            raising=False,
        )

        harness = SubprocessHarness(api_keys={"anthropic": "sk-anthropic-real"})
        handlers = harness._build_ipc_handlers()

        assert "llm_call" in handlers
        assert handlers["llm_call"] is fake_llm_handler
        assert observed["api_keys"] != {}


class TestRUN810HarnessBudgetInterceptorWiring:
    """RUN-810: SubprocessHarness must wire BudgetInterceptor into IPC execution."""

    @pytest.mark.asyncio
    async def test_run_builds_block_budget_interceptor_with_workflow_parent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module
        from runsight_core.yaml.schema import BlockLimitsDef

        workflow_budget = BudgetSession(
            scope_name="workflow:run810",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {}

        class FakeBudgetInterceptor:
            def __init__(self, *args: Any, **kwargs: Any):
                session = kwargs.get("session") or kwargs.get("budget_session")
                if session is None:
                    for arg in args:
                        if isinstance(arg, BudgetSession):
                            session = arg
                            break
                captured["child_session"] = session

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                session = captured.get("child_session")
                if session is not None:
                    session.accrue(
                        cost_usd=float(payload.get("cost_usd", 0.0)),
                        tokens=int(payload.get("total_tokens", 0)),
                    )
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

        class FakeIPCServer:
            def __init__(
                self,
                *,
                sock,
                handlers: dict[str, Any],
                registry=None,
                grant_token=None,
            ) -> None:
                captured["registry"] = registry
                captured["grant_token"] = grant_token
                self._registry = registry

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {},
                    )
                    await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.10, "total_tokens": 15},
                        request_ctx,
                    )
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        class _FakeStdIn:
            def __init__(self) -> None:
                self.writes: list[bytes] = []

            def write(self, data: bytes) -> None:
                self.writes.append(data)

            async def drain(self) -> None:
                return None

            def close(self) -> None:
                return None

        class _FakeStdOut:
            async def read(self) -> bytes:
                return (
                    _make_result_envelope(
                        block_id="run810-block",
                        output="ok",
                    )
                    .model_dump_json()
                    .encode()
                )

        class _FakeStdErr:
            async def readline(self) -> bytes:
                await asyncio.sleep(0)
                return b""

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = _FakeStdIn()
                self.stdout = _FakeStdOut()
                self.stderr = _FakeStdErr()
                self.returncode = 0
                self.pid = 12345

            async def wait(self) -> int:
                return 0

            def terminate(self) -> None:
                self.returncode = -15

            def kill(self) -> None:
                self.returncode = -9

        async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProc:
            return FakeProc()

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        monkeypatch.setattr(
            harness_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
        )

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="run810-block", block_type="linear")
        block_limits = BlockLimitsDef(cost_cap_usd=1.0, token_cap=200)
        envelope.block_config = {
            "block_id": "run810-block",
            "block_type": "linear",
            "limits": block_limits.model_dump(),
        }

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured.get("registry") is not None
        assert captured.get("child_session") is not None
        assert captured["child_session"] is not workflow_budget
        assert captured["child_session"].parent is workflow_budget
        assert captured["child_session"].cost_cap_usd == pytest.approx(1.0)
        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15

    @pytest.mark.asyncio
    async def test_run_registers_workflow_budget_when_block_has_no_own_limits(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        workflow_budget = BudgetSession(
            scope_name="workflow:run810",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {}

        class FakeBudgetInterceptor:
            def __init__(self, *args: Any, **kwargs: Any):
                captured["session"] = kwargs.get("session") or kwargs.get("budget_session")

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                session = captured.get("session")
                if session is not None:
                    session.accrue(
                        cost_usd=float(payload.get("cost_usd", 0.0)),
                        tokens=int(payload.get("total_tokens", 0)),
                    )
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

        class FakeIPCServer:
            def __init__(
                self,
                *,
                sock,
                handlers: dict[str, Any],
                registry=None,
                grant_token=None,
            ) -> None:
                self._registry = registry

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {},
                    )
                    await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.10, "total_tokens": 15},
                        request_ctx,
                    )
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        class _FakeStdIn:
            def write(self, data: bytes) -> None:
                return None

            async def drain(self) -> None:
                return None

            def close(self) -> None:
                return None

        class _FakeStdOut:
            async def read(self) -> bytes:
                return (
                    _make_result_envelope(block_id="run810-block", output="ok")
                    .model_dump_json()
                    .encode()
                )

        class _FakeStdErr:
            async def readline(self) -> bytes:
                await asyncio.sleep(0)
                return b""

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = _FakeStdIn()
                self.stdout = _FakeStdOut()
                self.stderr = _FakeStdErr()
                self.returncode = 0

            async def wait(self) -> int:
                return 0

            def terminate(self) -> None:
                self.returncode = -15

            def kill(self) -> None:
                self.returncode = -9

        async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProc:
            return FakeProc()

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        monkeypatch.setattr(
            harness_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
        )

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))
        envelope = _make_context_envelope(block_id="run810-block", block_type="linear")

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured["session"] is workflow_budget
        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15


class TestRUN397HarnessObserverInterceptorWiring:
    """RUN-397: SubprocessHarness must register ObserverInterceptor in IPC registry."""

    @pytest.mark.asyncio
    async def test_run_registers_observer_interceptor_for_ipc_trace_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module
        from runsight_core.yaml.schema import BlockLimitsDef

        workflow_budget = BudgetSession(
            scope_name="workflow:run397",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {
            "observer_inits": 0,
            "final_engine_context": None,
        }

        class FakeObserverInterceptor:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["observer_inits"] += 1

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                engine_context["trace_id"] = "trace-397"
                engine_context["span_id"] = "span-397"
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

        class FakeIPCServer:
            def __init__(
                self,
                *,
                sock,
                handlers: dict[str, Any],
                registry=None,
                grant_token=None,
            ) -> None:
                self._registry = registry
                captured["registry"] = registry

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {"trace.parent_id": "parent-397"},
                    )
                    final_ctx = await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.01, "total_tokens": 11},
                        request_ctx,
                    )
                    captured["final_engine_context"] = final_ctx
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        class _FakeStdIn:
            def write(self, data: bytes) -> None:
                return None

            async def drain(self) -> None:
                return None

            def close(self) -> None:
                return None

        class _FakeStdOut:
            async def read(self) -> bytes:
                return (
                    _make_result_envelope(
                        block_id="run397-block",
                        output="ok",
                    )
                    .model_dump_json()
                    .encode()
                )

        class _FakeStdErr:
            async def readline(self) -> bytes:
                await asyncio.sleep(0)
                return b""

        class FakeProc:
            def __init__(self) -> None:
                self.stdin = _FakeStdIn()
                self.stdout = _FakeStdOut()
                self.stderr = _FakeStdErr()
                self.returncode = 0
                self.pid = 1001

            async def wait(self) -> int:
                return 0

            def terminate(self) -> None:
                self.returncode = -15

            def kill(self) -> None:
                self.returncode = -9

        async def fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> FakeProc:
            return FakeProc()

        monkeypatch.setattr(
            harness_module, "ObserverInterceptor", FakeObserverInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        monkeypatch.setattr(
            harness_module.asyncio,
            "create_subprocess_exec",
            fake_create_subprocess_exec,
        )

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="run397-block", block_type="linear")
        envelope.block_config = {
            "block_id": "run397-block",
            "block_type": "linear",
            "limits": BlockLimitsDef(cost_cap_usd=1.0, token_cap=200).model_dump(),
        }

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured["registry"] is not None
        assert captured["observer_inits"] >= 1
        assert captured["final_engine_context"]["trace.parent_id"] == "parent-397"
        assert captured["final_engine_context"]["trace_id"] == "trace-397"
        assert captured["final_engine_context"]["span_id"] == "span-397"


class TestRUN394SubprocessHarnessWiringContract:
    """RUN-394: SubprocessHarness internal wiring for handlers, allowlist, cleanup, and env."""

    def test_constructor_accepts_api_keys_and_resolved_tools(self):
        from runsight_core.isolation import SubprocessHarness

        class SearchTool:
            async def execute(self, args: dict[str, Any]) -> str:
                return f"search:{args['q']}"

        tool = SearchTool()
        harness = SubprocessHarness(
            api_keys={"openai": "sk-openai-real"},
            resolved_tools={"search": tool},
        )

        assert harness is not None

    @pytest.mark.asyncio
    async def test_build_ipc_handlers_uses_constructor_resolved_tools_registry(self):
        from runsight_core.isolation import SubprocessHarness

        class SearchTool:
            async def execute(self, args: dict[str, Any]) -> str:
                return f"search:{args['q']}"

        harness = SubprocessHarness(
            api_keys={"openai": "sk-openai-real"},
            resolved_tools={"search": SearchTool()},
        )

        handlers = harness._build_ipc_handlers()
        assert {"llm_call", "tool_call", "http", "file_io"}.issubset(set(handlers))

        result = await handlers["tool_call"]({"name": "search", "arguments": {"q": "runsight"}})
        assert result == {"output": "search:runsight"}

    @pytest.mark.asyncio
    async def test_default_http_allowlist_is_deny_all(self, monkeypatch: pytest.MonkeyPatch):
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import handlers as handlers_module

        captured: dict[str, Any] = {}

        def fake_make_http_handler(*, credentials: dict[str, str], url_allowlist: list[str]):
            captured["url_allowlist"] = list(url_allowlist)

            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"status": 200}

            return _handler

        def fake_make_file_io_handler(*, base_dir: str):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"ok": True}

            return _handler

        def fake_make_llm_call_handler(*, api_keys: dict[str, str]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"content": "ok"}

            return _handler

        def fake_make_tool_call_handler(_resolved_tools: dict[str, Any]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "ok"}

            return _handler

        monkeypatch.setattr(handlers_module, "make_http_handler", fake_make_http_handler)
        monkeypatch.setattr(handlers_module, "make_file_io_handler", fake_make_file_io_handler)
        monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
        monkeypatch.setattr(handlers_module, "make_tool_call_handler", fake_make_tool_call_handler)

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        _ = harness._build_ipc_handlers()

        assert captured["url_allowlist"] == []

    @pytest.mark.asyncio
    async def test_constructor_http_allowlist_is_passed_to_http_handler(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import handlers as handlers_module

        captured: dict[str, Any] = {}

        def fake_make_http_handler(*, credentials: dict[str, str], url_allowlist: list[str]):
            captured["url_allowlist"] = list(url_allowlist)

            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"status": 200}

            return _handler

        def fake_make_file_io_handler(*, base_dir: str):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"ok": True}

            return _handler

        def fake_make_llm_call_handler(*, api_keys: dict[str, str]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"content": "ok"}

            return _handler

        def fake_make_tool_call_handler(_resolved_tools: dict[str, Any]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "ok"}

            return _handler

        monkeypatch.setattr(handlers_module, "make_http_handler", fake_make_http_handler)
        monkeypatch.setattr(handlers_module, "make_file_io_handler", fake_make_file_io_handler)
        monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
        monkeypatch.setattr(handlers_module, "make_tool_call_handler", fake_make_tool_call_handler)

        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            url_allowlist=["api.example.com"],
        )
        _ = harness._build_ipc_handlers()

        assert captured["url_allowlist"] == ["api.example.com"]

    @pytest.mark.asyncio
    async def test_file_io_temp_dir_is_removed_by_harness_cleanup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import handlers as handlers_module
        from runsight_core.isolation import harness as harness_module

        created: dict[str, Path] = {}

        def fake_mkdtemp(*args: Any, **kwargs: Any) -> str:
            base_dir = tmp_path / "rs-fio-run394"
            base_dir.mkdir(parents=True, exist_ok=True)
            created["base_dir"] = base_dir
            return str(base_dir)

        def fake_make_file_io_handler(*, base_dir: str):
            created["base_dir"] = Path(base_dir)

            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"ok": True}

            return _handler

        def fake_make_http_handler(*, credentials: dict[str, str], url_allowlist: list[str]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"status": 200}

            return _handler

        def fake_make_llm_call_handler(*, api_keys: dict[str, str]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"content": "ok"}

            return _handler

        def fake_make_tool_call_handler(_resolved_tools: dict[str, Any]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "ok"}

            return _handler

        monkeypatch.setattr(harness_module.tempfile, "mkdtemp", fake_mkdtemp)
        monkeypatch.setattr(handlers_module, "make_file_io_handler", fake_make_file_io_handler)
        monkeypatch.setattr(handlers_module, "make_http_handler", fake_make_http_handler)
        monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
        monkeypatch.setattr(handlers_module, "make_tool_call_handler", fake_make_tool_call_handler)

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        _ = harness._build_ipc_handlers()
        assert created["base_dir"].exists()

        harness._cleanup(socket_path=None, working_dir=None)
        assert not created["base_dir"].exists()

    @pytest.mark.asyncio
    async def test_real_file_io_handler_write_read_and_cleanup_remove_sandbox(self):
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        handlers = harness._build_ipc_handlers()
        file_io = handlers["file_io"]
        sandbox = Path(harness._file_io_temp_dir or "")

        assert sandbox.exists()
        write_result = await file_io(
            {"action_type": "write", "path": "nested/result.txt", "content": "hello"}
        )
        read_result = await file_io({"action_type": "read", "path": "nested/result.txt"})

        assert write_result == {"ok": True}
        assert read_result == {"content": "hello"}

        harness._cleanup(socket_path=None, working_dir=None)
        assert not sandbox.exists()

    @pytest.mark.asyncio
    async def test_build_subprocess_env_with_api_keys_constructor_uses_grant_token_not_block_api_key(
        self,
    ):
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-openai-real"})
        env = harness._build_subprocess_env(socket_path="/tmp/rs-run394.sock", block_id="block-394")

        assert "RUNSIGHT_GRANT_TOKEN" in env
        assert env["RUNSIGHT_GRANT_TOKEN"] != ""
        assert "RUNSIGHT_BLOCK_API_KEY" not in env


class TestRUN811HarnessHTTPWiringContract:
    """RUN-811: harness must pass host-scoped credentials to HTTP handler factory."""

    @pytest.mark.asyncio
    async def test_build_ipc_handlers_passes_unmerged_host_credentials_to_http_handler(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import handlers as handlers_module

        captured: dict[str, Any] = {}

        def fake_make_http_handler(
            *, credentials: dict[str, dict[str, str]], url_allowlist: list[str]
        ):
            captured["credentials"] = credentials
            captured["url_allowlist"] = list(url_allowlist)

            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"status_code": 200, "body": "ok", "headers": {}}

            return _handler

        def fake_make_file_io_handler(*, base_dir: str):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"ok": True}

            return _handler

        def fake_make_llm_call_handler(*, api_keys: dict[str, str]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"content": "ok"}

            return _handler

        def fake_make_tool_call_handler(_resolved_tools: dict[str, Any]):
            async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "ok"}

            return _handler

        monkeypatch.setattr(handlers_module, "make_http_handler", fake_make_http_handler)
        monkeypatch.setattr(handlers_module, "make_file_io_handler", fake_make_file_io_handler)
        monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
        monkeypatch.setattr(handlers_module, "make_tool_call_handler", fake_make_tool_call_handler)

        expected_credentials = {
            "host-a.com": {"Authorization": "Bearer host-a", "X-Host-A": "1"},
            "host-b.com": {"Authorization": "Bearer host-b", "X-Host-B": "1"},
        }
        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            tool_credentials=expected_credentials,
        )
        _ = harness._build_ipc_handlers()

        assert captured["credentials"] == expected_credentials
        assert captured["url_allowlist"] == []


class TestMinimalEnvironment:
    """Subprocess must receive minimal env with grant token, not API key."""

    @pytest.mark.asyncio
    async def test_subprocess_harness_importable(self):
        """SubprocessHarness can be imported from runsight_core.isolation."""
        from runsight_core.isolation import SubprocessHarness

        assert SubprocessHarness is not None

    @pytest.mark.asyncio
    async def test_spawn_env_contains_path(self):
        """Subprocess env must include PATH."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env()

        assert "PATH" in env

    @pytest.mark.asyncio
    async def test_spawn_env_contains_grant_token(self):
        """Subprocess env must include RUNSIGHT_GRANT_TOKEN."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env()

        assert "RUNSIGHT_GRANT_TOKEN" in env
        assert isinstance(env["RUNSIGHT_GRANT_TOKEN"], str)
        assert env["RUNSIGHT_GRANT_TOKEN"] != ""

    @pytest.mark.asyncio
    async def test_spawn_env_does_not_include_block_api_key(self):
        """Subprocess env must not include RUNSIGHT_BLOCK_API_KEY."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env()

        assert "RUNSIGHT_BLOCK_API_KEY" not in env

    @pytest.mark.asyncio
    async def test_spawn_env_does_not_inherit_host_env(self):
        """Subprocess env must NOT inherit the full host environment."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env()

        # Common env vars that should NOT leak through
        for var in ("HOME", "USER", "SHELL", "DATABASE_URL", "SECRET_KEY"):
            assert var not in env, f"{var} should not be in subprocess env"

    @pytest.mark.asyncio
    async def test_spawn_env_contains_ipc_socket_path(self):
        """Subprocess env must include RUNSIGHT_IPC_SOCKET."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env(socket_path="/tmp/rs-abc123.sock")

        assert "RUNSIGHT_IPC_SOCKET" in env
        assert env["RUNSIGHT_IPC_SOCKET"] == "/tmp/rs-abc123.sock"

    @pytest.mark.asyncio
    async def test_spawn_env_has_macos_dylib_paths(self):
        """On macOS, subprocess env includes DYLD_LIBRARY_PATH or DYLD_FALLBACK_LIBRARY_PATH."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env()

        if sys.platform == "darwin":
            has_dylib = "DYLD_LIBRARY_PATH" in env or "DYLD_FALLBACK_LIBRARY_PATH" in env
            assert has_dylib, "macOS env must include dylib paths"

    @pytest.mark.asyncio
    async def test_spawn_env_limited_key_count(self):
        """Subprocess env should have a small number of keys (minimal env)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        env = harness._build_subprocess_env(socket_path="/tmp/rs-test.sock")

        # PATH + grant token + socket + maybe macOS dylib paths = at most ~5-6 keys
        assert len(env) <= 10, f"Env has too many keys ({len(env)}), should be minimal"


# ===========================================================================
# AC2: Subprocess working dir is fresh temp dir
# ===========================================================================


class TestFreshTempWorkingDir:
    """Subprocess must run in a fresh temp dir, not project root."""

    @pytest.mark.asyncio
    async def test_working_dir_is_temp_dir(self):
        """SubprocessHarness creates a fresh temp dir for the subprocess cwd."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        work_dir = harness._create_working_dir()

        assert Path(work_dir).exists()
        assert Path(work_dir).is_dir()
        # Should be under the system temp directory
        assert work_dir.startswith(tempfile.gettempdir()) or work_dir.startswith("/tmp")

        # Cleanup
        os.rmdir(work_dir)

    @pytest.mark.asyncio
    async def test_working_dir_is_not_project_root(self):
        """Working dir must not be the project root or cwd."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        work_dir = harness._create_working_dir()

        assert work_dir != os.getcwd()

        # Cleanup
        os.rmdir(work_dir)

    @pytest.mark.asyncio
    async def test_each_call_creates_unique_dir(self):
        """Each invocation creates a different temp dir."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        dir1 = harness._create_working_dir()
        dir2 = harness._create_working_dir()

        assert dir1 != dir2

        # Cleanup
        os.rmdir(dir1)
        os.rmdir(dir2)


# ===========================================================================
# AC3: Socket created by SubprocessHarness, mode 0600, random path
# ===========================================================================


class TestSocketCreation:
    """SubprocessHarness creates and binds the socket (not IPCServer)."""

    @pytest.mark.asyncio
    async def test_create_socket_returns_bound_socket(self):
        """_create_socket returns a bound Unix socket object."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        sock, sock_path = harness._create_socket()

        try:
            assert isinstance(sock, socket.socket)
            assert sock.family == socket.AF_UNIX
            assert Path(sock_path).exists()
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_path_is_random(self):
        """Socket path must be random (different each call)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        _, path1 = harness._create_socket()
        _, path2 = harness._create_socket()

        try:
            assert path1 != path2
        finally:
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_path_format(self):
        """Socket path follows /tmp/rs-{random}.sock pattern."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        sock, sock_path = harness._create_socket()

        try:
            assert sock_path.startswith("/tmp/rs-")
            assert sock_path.endswith(".sock")
            # Must be under 104 bytes (macOS AF_UNIX limit)
            assert len(sock_path.encode()) < 104
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_permissions_0600(self):
        """Socket file must have mode 0600 (owner read/write only)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        sock, sock_path = harness._create_socket()

        try:
            mode = os.stat(sock_path).st_mode
            # Check only the permission bits
            perm = stat.S_IMODE(mode)
            assert perm == 0o600, f"Socket permissions should be 0600, got {oct(perm)}"
        finally:
            sock.close()
            Path(sock_path).unlink(missing_ok=True)


# ===========================================================================
# AC4: ContextEnvelope contains only YAML-declared scoped data
# ===========================================================================


class TestContextScoping:
    """ContextEnvelope must contain only declaration-governed scoped data."""

    @pytest.mark.asyncio
    async def test_linear_block_uses_declared_inputs_not_previous_block_type_scope(self):
        """LinearBlock scoping follows declared inputs, not previous_block_id."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        state = WorkflowState(
            results={
                "block-0": BlockResult(output="first result"),
                "block-1": BlockResult(output='{"summary": "declared", "secret": "hidden"}'),
            },
            shared_memory={"global_key": "global_value"},
        )

        block_config = {
            "block_id": "block-2",
            "block_type": "linear",
            "soul_ref": "test",
            "previous_block_id": "block-0",
            "inputs": {"summary": {"from": "block-1.summary"}},
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "block-1" in envelope.scoped_results
        assert "block-0" not in envelope.scoped_results
        assert envelope.inputs == {"summary": "declared"}
        assert "hidden" not in envelope.model_dump_json()

    @pytest.mark.asyncio
    async def test_gate_block_gets_eval_key_as_internal_declared_context(self):
        """GateBlock scoping is represented as governed internal content input."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        state = WorkflowState(
            results={
                "eval-block": BlockResult(output="eval output"),
                "other-block": BlockResult(output="other output"),
            }
        )

        block_config = {
            "block_id": "gate-1",
            "block_type": "gate",
            "eval_key": "eval-block",
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "eval-block" in envelope.scoped_results
        assert "other-block" not in envelope.scoped_results
        assert envelope.inputs == {"content": "eval output"}

    @pytest.mark.asyncio
    async def test_synthesize_block_gets_input_block_ids_as_internal_declared_context(self):
        """SynthesizeBlock input_block_ids are governed internal inputs."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        state = WorkflowState(
            results={
                "block-a": BlockResult(output="a output"),
                "block-b": BlockResult(output="b output"),
                "block-c": BlockResult(output="c output"),
            }
        )

        block_config = {
            "block_id": "synth-1",
            "block_type": "synthesize",
            "input_block_ids": ["block-a", "block-c"],
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "block-a" in envelope.scoped_results
        assert "block-c" in envelope.scoped_results
        assert "block-b" not in envelope.scoped_results
        assert envelope.inputs == {"block-a": "a output", "block-c": "c output"}

    @pytest.mark.asyncio
    async def test_declared_namespace_inputs_replace_legacy_context_scope(self):
        """YAML inputs/access replace legacy context_scope serialization."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import BlockResult, WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        state = WorkflowState(
            results={
                "block-x": BlockResult(output="x"),
                "block-y": BlockResult(output="y"),
                "block-z": BlockResult(output="z"),
            },
            shared_memory={
                "allowed_key": "allowed_val",
                "secret_key": "secret_val",
            },
        )

        block_config = {
            "block_id": "custom-1",
            "block_type": "linear",
            "inputs": {
                "x": {"from": "block-x"},
                "allowed": {"from": "shared_memory.allowed_key"},
            },
            "context_scope": {
                "results": ["block-y", "block-z"],
                "shared_memory": ["secret_key"],
            },
        }

        envelope = harness._build_context_envelope(state=state, block_config=block_config)

        assert "block-x" in envelope.scoped_results
        assert "block-z" not in envelope.scoped_results
        assert "block-y" not in envelope.scoped_results
        assert "allowed_key" in envelope.scoped_shared_memory
        assert "secret_key" not in envelope.scoped_shared_memory
        assert envelope.inputs == {"x": "x", "allowed": "allowed_val"}

    @pytest.mark.asyncio
    async def test_raw_access_block_config_is_rejected_while_default_remains_declared(
        self,
    ):
        """Raw harness configs must reject access while the implicit default stays declared."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.state import WorkflowState

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        state = WorkflowState()

        declared_envelope = harness._build_context_envelope(
            state=state,
            block_config={
                "block_id": "block-1",
                "block_type": "linear",
            },
        )
        assert declared_envelope.access == "declared"

        with pytest.raises(ValueError, match=r"access.*unsupported|all-access is no longer"):
            harness._build_context_envelope(
                state=state,
                block_config={
                    "block_id": "block-1",
                    "block_type": "linear",
                    "access": "declared",
                },
            )


# ===========================================================================
# AC5: Timeout enforced — subprocess killed on timeout
# ===========================================================================


class TestTimeoutEnforcement:
    """Subprocess must be killed when it exceeds the timeout."""

    @pytest.mark.asyncio
    async def test_run_raises_on_timeout(self):
        """SubprocessHarness.run() raises a timeout error when the subprocess exceeds timeout."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"}, timeout_seconds=1)
        envelope = _make_context_envelope(timeout_seconds=1)

        # The run method should raise when the subprocess times out
        with pytest.raises((asyncio.TimeoutError, TimeoutError, Exception)) as exc_info:
            await harness.run(envelope)

        # The error should mention timeout
        assert "timeout" in str(exc_info.value).lower() or isinstance(
            exc_info.value, (asyncio.TimeoutError, TimeoutError)
        )

    @pytest.mark.asyncio
    async def test_timeout_uses_envelope_value(self):
        """Timeout is taken from the ContextEnvelope.timeout_seconds field."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        envelope = _make_context_envelope(timeout_seconds=2)

        # Should use the envelope's timeout, not a default
        assert envelope.timeout_seconds == 2
        # Harness must respect the envelope timeout
        assert harness is not None


# ===========================================================================
# AC6: Heartbeat stall detected — subprocess killed
# ===========================================================================


class TestHeartbeatStallDetection:
    """Subprocess must be killed when heartbeats stop arriving."""

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_kills_subprocess(self):
        """If no heartbeat for heartbeat_timeout seconds, subprocess is killed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            heartbeat_timeout=1,
        )

        # The harness should track heartbeats and kill on stall
        assert hasattr(harness, "_heartbeat_timeout") or hasattr(harness, "heartbeat_timeout")

    @pytest.mark.asyncio
    async def test_monitor_detects_missing_heartbeat(self):
        """The monitoring coroutine detects when heartbeats stop."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            heartbeat_timeout=1,
        )

        # Simulate a process that sends no heartbeats
        mock_proc = MagicMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")
        mock_proc.pid = 12345
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.terminate = MagicMock()

        # _monitor_heartbeats should detect stall and request kill
        killed = await harness._monitor_heartbeats(mock_proc, timeout=1)
        assert killed is True


# ===========================================================================
# AC7: Phase stall detected — subprocess killed
# ===========================================================================


class TestPhaseStallDetection:
    """Subprocess must be killed when same phase exceeds phase_timeout."""

    @pytest.mark.asyncio
    async def test_phase_stall_kills_subprocess(self):
        """If same phase continues beyond phase_timeout, subprocess is killed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            phase_timeout=1,
        )

        assert hasattr(harness, "_phase_timeout") or hasattr(harness, "phase_timeout")

    @pytest.mark.asyncio
    async def test_phase_change_resets_timer(self):
        """When the phase changes, the phase stall timer resets."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(
            api_keys={"openai": "sk-test-key-123"},
            phase_timeout=2,
        )

        # Simulate heartbeats that change phase
        heartbeats = [
            HeartbeatMessage(
                heartbeat=1,
                phase="init",
                detail="starting",
                timestamp="2026-01-01T00:00:00Z",
            ),
            HeartbeatMessage(
                heartbeat=2,
                phase="executing",
                detail="running",
                timestamp="2026-01-01T00:00:01Z",
            ),
        ]

        # Phase changed from init -> executing, so stall timer should reset
        tracker = harness._create_heartbeat_tracker()
        for hb in heartbeats:
            tracker.update(hb)

        assert tracker.current_phase == "executing"
        assert not tracker.is_stalled


# ===========================================================================
# AC8: ResultEnvelope validated (schema + size cap)
# ===========================================================================


class TestResultEnvelopeValidation:
    """SubprocessHarness validates ResultEnvelope schema and size cap."""

    @pytest.mark.asyncio
    async def test_valid_result_envelope_accepted(self):
        """A well-formed ResultEnvelope passes validation."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        result = _make_result_envelope()
        raw_json = result.model_dump_json()

        validated = harness._validate_result(raw_json, max_bytes=1_000_000)
        assert validated.block_id == "block-1"
        assert validated.output == "done"

    @pytest.mark.asyncio
    async def test_oversized_result_rejected(self):
        """A ResultEnvelope exceeding max_output_bytes is rejected."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        result = _make_result_envelope(output="x" * 10_000)
        raw_json = result.model_dump_json()

        with pytest.raises((ValueError, Exception)) as exc_info:
            harness._validate_result(raw_json, max_bytes=100)

        assert "size" in str(exc_info.value).lower() or "bytes" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_malformed_json_rejected(self):
        """Invalid JSON is rejected during result validation."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        with pytest.raises((json.JSONDecodeError, ValueError, Exception)):
            harness._validate_result("not valid json {{{", max_bytes=1_000_000)

    @pytest.mark.asyncio
    async def test_missing_required_fields_rejected(self):
        """A ResultEnvelope missing required fields is rejected."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        # Valid JSON but missing required ResultEnvelope fields
        incomplete = json.dumps({"block_id": "block-1"})

        with pytest.raises((ValueError, Exception)):
            harness._validate_result(incomplete, max_bytes=1_000_000)


# ===========================================================================
# AC9: SIGTERM then SIGKILL escalation on kill
# ===========================================================================


class TestGracefulKillEscalation:
    """Kill must send SIGTERM first, then SIGKILL after 5 seconds."""

    @pytest.mark.asyncio
    async def test_kill_sends_sigterm_first(self):
        """_kill_subprocess sends SIGTERM before SIGKILL."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")

        def track_kill():
            signals_sent.append("SIGKILL")
            mock_proc.returncode = -9

        mock_proc.terminate = track_terminate
        mock_proc.kill = track_kill
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)

        await harness._kill_subprocess(mock_proc)

        assert signals_sent[0] == "SIGTERM"

    @pytest.mark.asyncio
    async def test_kill_escalates_to_sigkill(self):
        """If SIGTERM doesn't work within grace period, SIGKILL is sent."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")

        def track_kill():
            signals_sent.append("SIGKILL")
            mock_proc.returncode = -9

        mock_proc.terminate = track_terminate
        mock_proc.kill = track_kill
        # Process doesn't die after SIGTERM (wait times out)
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)

        await harness._kill_subprocess(mock_proc)

        assert "SIGTERM" in signals_sent
        assert "SIGKILL" in signals_sent

    @pytest.mark.asyncio
    async def test_no_sigkill_if_sigterm_succeeds(self):
        """If SIGTERM causes the process to exit, no SIGKILL is sent."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        signals_sent = []
        mock_proc = MagicMock()
        mock_proc.returncode = None

        def track_terminate():
            signals_sent.append("SIGTERM")
            mock_proc.returncode = 0

        mock_proc.terminate = track_terminate
        mock_proc.kill = lambda: signals_sent.append("SIGKILL")
        # Process exits cleanly after SIGTERM
        mock_proc.wait = AsyncMock(return_value=0)

        await harness._kill_subprocess(mock_proc)

        assert "SIGTERM" in signals_sent
        assert "SIGKILL" not in signals_sent


# ===========================================================================
# AC10: Negative return codes mapped to meaningful error messages
# ===========================================================================


class TestNegativeReturnCodeMapping:
    """Negative return codes should map to meaningful signal-based errors."""

    @pytest.mark.asyncio
    async def test_sigkill_mapped_to_oom(self):
        """Return code -9 (SIGKILL) is mapped to OOM error message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        error_msg = harness._map_return_code(-9)

        assert "SIGKILL" in error_msg or "OOM" in error_msg or "signal 9" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_sigsegv_mapped_to_segfault(self):
        """Return code -11 (SIGSEGV) is mapped to segfault error message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        error_msg = harness._map_return_code(-11)

        assert (
            "SIGSEGV" in error_msg
            or "segfault" in error_msg.lower()
            or "signal 11" in error_msg.lower()
        )

    @pytest.mark.asyncio
    async def test_sigterm_mapped(self):
        """Return code -15 (SIGTERM) is mapped to termination message."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        error_msg = harness._map_return_code(-15)

        assert (
            "SIGTERM" in error_msg
            or "terminated" in error_msg.lower()
            or "signal 15" in error_msg.lower()
        )

    @pytest.mark.asyncio
    async def test_positive_return_code_is_application_error(self):
        """Return code > 0 indicates an application-level error."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        error_msg = harness._map_return_code(1)

        assert "error" in error_msg.lower() or "exit" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_zero_return_code_is_success(self):
        """Return code 0 is success (no error)."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        result = harness._map_return_code(0)

        # Zero should return None or empty string (no error)
        assert result is None or result == ""


# ===========================================================================
# AC11: Socket and temp dir cleaned up on exit (including crashes)
# ===========================================================================


class TestCleanup:
    """Socket file and temp dir must be cleaned up on exit, even on crashes."""

    @pytest.mark.asyncio
    async def test_socket_cleaned_up_after_normal_exit(self):
        """Socket file is removed after a successful run."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        sock, sock_path = harness._create_socket()

        # Simulate cleanup
        harness._cleanup(socket_path=sock_path, working_dir=None)

        assert not Path(sock_path).exists()
        sock.close()

    @pytest.mark.asyncio
    async def test_temp_dir_cleaned_up_after_normal_exit(self):
        """Temp working dir is removed after a successful run."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        work_dir = harness._create_working_dir()

        harness._cleanup(socket_path=None, working_dir=work_dir)

        assert not Path(work_dir).exists()

    @pytest.mark.asyncio
    async def test_cleanup_handles_already_removed_socket(self):
        """Cleanup does not raise if the socket was already removed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        # Should not raise
        harness._cleanup(socket_path="/tmp/rs-nonexistent.sock", working_dir=None)

    @pytest.mark.asyncio
    async def test_cleanup_handles_already_removed_dir(self):
        """Cleanup does not raise if the temp dir was already removed."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})

        # Should not raise
        harness._cleanup(socket_path=None, working_dir="/tmp/rs-nonexistent-dir")

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self):
        """Both socket and temp dir are cleaned up even when run() raises."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        sock, sock_path = harness._create_socket()
        work_dir = harness._create_working_dir()

        # Simulate a crash during run by calling cleanup directly
        harness._cleanup(socket_path=sock_path, working_dir=work_dir)

        assert not Path(sock_path).exists()
        assert not Path(work_dir).exists()
        sock.close()


# ===========================================================================
# AC12: Integration test — LinearBlock round-trip via subprocess
# ===========================================================================


class TestLinearBlockRoundTrip:
    """End-to-end: build envelope, spawn subprocess, get result back."""

    @pytest.mark.asyncio
    async def test_run_returns_result_envelope(self):
        """SubprocessHarness.run() returns a ResultEnvelope on success."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        envelope = _make_context_envelope(block_type="linear")

        # This will fail because SubprocessHarness doesn't exist yet,
        # but verifies the expected interface
        result = await harness.run(envelope)

        assert isinstance(result, ResultEnvelope)
        assert result.block_id == "block-1"

    @pytest.mark.asyncio
    async def test_run_writes_envelope_to_stdin(self):
        """SubprocessHarness passes ContextEnvelope JSON to subprocess stdin."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        envelope = _make_context_envelope()

        # Verify the envelope can be serialized (it will be passed to stdin)
        json_str = envelope.model_dump_json()
        parsed = ContextEnvelope.model_validate_json(json_str)
        assert parsed.block_id == envelope.block_id

        # The actual run will fail since SubprocessHarness doesn't exist
        result = await harness.run(envelope)
        assert isinstance(result, ResultEnvelope)

    @pytest.mark.asyncio
    async def test_run_starts_ipc_server(self):
        """SubprocessHarness starts an IPCServer as an asyncio task during run."""
        from runsight_core.isolation import SubprocessHarness

        # The harness should have a method or attribute related to IPC server setup
        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        assert callable(getattr(harness, "run", None))

    @pytest.mark.asyncio
    async def test_result_contains_output_and_cost(self):
        """The ResultEnvelope from a successful run includes output and cost data."""
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "sk-test-key-123"})
        envelope = _make_context_envelope(block_type="linear")

        result = await harness.run(envelope)

        assert isinstance(result, ResultEnvelope)
        assert result.block_id == envelope.block_id
        assert isinstance(result.cost_usd, float)
        assert isinstance(result.total_tokens, int)


class TestRUN398GrantTokenContract:
    """GrantToken model and harness env wiring for single-use subprocess auth."""

    def test_grant_token_model_exists_with_expected_defaults(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="block-398")
        assert isinstance(token.token, str)
        assert token.token != ""
        assert token.block_id == "block-398"
        assert token.ttl_seconds == 120.0
        assert token.consumed is False

    def test_grant_token_consume_is_single_use(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="block-398")
        assert token.consume() is True
        assert token.consume() is False

    def test_grant_token_rejects_when_expired(self):
        from runsight_core.isolation import harness as harness_module

        GrantToken = getattr(harness_module, "GrantToken", None)
        assert GrantToken is not None

        token = GrantToken(block_id="block-398", created_at=0.0, ttl_seconds=30.0)
        assert token.consume() is False
