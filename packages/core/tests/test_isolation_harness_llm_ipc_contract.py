"""Subprocess harness LLM IPC contract behavior."""

from __future__ import annotations

from typing import Any

import pytest
from isolation_harness_helpers import (
    _fixture_url,
)

pytestmark = pytest.mark.real_subprocess_isolation


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
