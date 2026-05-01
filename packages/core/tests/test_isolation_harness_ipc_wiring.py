"""SubprocessHarness IPC handler and wiring contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from isolation_harness_helpers import (
    _fixture_url,
    _make_context_envelope,
    _make_result_envelope,
    _patch_harness_subprocess_result,
    _socket_fixture_path,
    _tool_call_passthrough,
)
from runsight_core.isolation import (
    ResultEnvelope,
)


class TestIpcHandlerRegistration:
    """Harness should register all engine-side IPC handlers, including generic tool_call."""

    @pytest.mark.asyncio
    async def test_build_ipc_handlers_keeps_http_and_file_io_and_adds_tool_call(self):
        """Harness exposes tool_call without regressing existing handlers."""
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.tools import ToolInstance

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
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


class TestLLMCallHandlerContract:
    """Engine-side llm_call handler factory and harness registration contract."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model_name", "api_keys", "expected_key"),
        [
            (
                "claude-sonnet-4-20250514",
                {"anthropic": "dummy-anthropic-key", "openai": "dummy-openai-key"},
                "dummy-anthropic-key",
            ),
            (
                "gpt-4o-mini",
                {"anthropic": "dummy-anthropic-key", "openai": "dummy-openai-key"},
                "dummy-openai-key",
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
                "api_base": _fixture_url(),
                "base_url": _fixture_url(),
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

        handler = make_llm_call_handler(api_keys={"anthropic": "dummy-anthropic-key"})
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

        harness = SubprocessHarness(api_keys={"anthropic": "dummy-anthropic-key"})
        handlers = harness._build_ipc_handlers()

        assert "llm_call" in handlers
        assert handlers["llm_call"] is fake_llm_handler
        assert observed["api_keys"] != {}


class TestHarnessBudgetInterceptorWiring:
    """SubprocessHarness wires BudgetInterceptor into IPC execution."""

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
            scope_name="workflow:harness-budget-parent",
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

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="budgeted-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="budgeted-linear-block", block_type="linear")
        block_limits = BlockLimitsDef(cost_cap_usd=1.0, token_cap=200)
        envelope.block_config = {
            "block_id": "budgeted-linear-block",
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
            scope_name="workflow:harness-budget-parent",
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

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="budgeted-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))
        envelope = _make_context_envelope(block_id="budgeted-linear-block", block_type="linear")

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured["session"] is workflow_budget
        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15


class TestHarnessObserverInterceptorWiring:
    """SubprocessHarness registers ObserverInterceptor in IPC registry."""

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
            scope_name="workflow:harness-observer-parent",
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
                engine_context["trace_id"] = "observer-trace"
                engine_context["span_id"] = "observer-span"
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
                        {"trace.parent_id": "observer-parent-span"},
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

        monkeypatch.setattr(
            harness_module, "ObserverInterceptor", FakeObserverInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="observed-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="observed-linear-block", block_type="linear")
        envelope.block_config = {
            "block_id": "observed-linear-block",
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
        assert captured["final_engine_context"]["trace.parent_id"] == "observer-parent-span"
        assert captured["final_engine_context"]["trace_id"] == "observer-trace"
        assert captured["final_engine_context"]["span_id"] == "observer-span"


class TestSubprocessHarnessWiringContract:
    """SubprocessHarness internal wiring for handlers, allowlist, cleanup, and env."""

    def test_constructor_accepts_api_keys_and_resolved_tools(self):
        from runsight_core.isolation import SubprocessHarness

        class SearchTool:
            async def execute(self, args: dict[str, Any]) -> str:
                return f"search:{args['q']}"

        tool = SearchTool()
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
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
            api_keys={"openai": "dummy-openai-key"},
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

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
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
            api_keys={"openai": "dummy-openai-key"},
            url_allowlist=["api-fixture.test"],
        )
        _ = harness._build_ipc_handlers()

        assert captured["url_allowlist"] == ["api-fixture.test"]

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
            base_dir = tmp_path / "rs-fio-harness"
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

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        _ = harness._build_ipc_handlers()
        assert created["base_dir"].exists()

        harness._cleanup(socket_path=None, working_dir=None)
        assert not created["base_dir"].exists()

    @pytest.mark.asyncio
    async def test_real_file_io_handler_write_read_and_cleanup_remove_sandbox(self):
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
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
        tmp_path: Path,
    ):
        from runsight_core.isolation import SubprocessHarness

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        env = harness._build_subprocess_env(
            socket_path=_socket_fixture_path(tmp_path, "rs-harness.sock"),
            block_id="env-linear-block",
        )

        assert "RUNSIGHT_GRANT_TOKEN" in env
        assert env["RUNSIGHT_GRANT_TOKEN"] != ""
        assert "RUNSIGHT_BLOCK_API_KEY" not in env


class TestHarnessHTTPWiringContract:
    """Harness passes host-scoped credentials to HTTP handler factory."""

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
            "host-a.fixture.test": {"Authorization": "Bearer host-a", "X-Host-A": "1"},
            "host-b.fixture.test": {"Authorization": "Bearer host-b", "X-Host-B": "1"},
        }
        harness = SubprocessHarness(
            api_keys={"openai": "dummy-openai-key"},
            tool_credentials=expected_credentials,
        )
        _ = harness._build_ipc_handlers()

        assert captured["credentials"] == expected_credentials
        assert captured["url_allowlist"] == []
