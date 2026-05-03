"""Subprocess harness runtime contract behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from isolation_harness_helpers import (
    _socket_fixture_path,
)

pytestmark = pytest.mark.real_subprocess_isolation


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
