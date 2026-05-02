"""Subprocess harness HTTP wiring behavior."""

from __future__ import annotations

from typing import Any

import pytest


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
