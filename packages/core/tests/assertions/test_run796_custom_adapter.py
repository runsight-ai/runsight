"""Red tests for RUN-796: custom assertion adapter class builder."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any

import pytest
from runsight_core.assertions.base import AssertionContext, GradingResult


def _load_symbols():
    module = importlib.import_module("runsight_core.assertions.custom")
    return module, module._build_adapter_class


def _make_context(**overrides: Any) -> AssertionContext:
    defaults = dict(
        output="needle in haystack",
        prompt="Find the launch blocker.",
        prompt_hash="prompt-hash-123",
        soul_id="soul-1",
        soul_version="v7",
        block_id="block-a",
        block_type="LinearBlock",
        cost_usd=0.031,
        total_tokens=321,
        latency_ms=245.5,
        variables={"topic": "launch", "severity": "high"},
        run_id="run-123",
        workflow_id="wf-456",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


@dataclass
class _FakeProc:
    stdout_payload: bytes
    stderr_payload: bytes = b""
    returncode: int = 0

    async def communicate(self, input: bytes | None = None):
        return self.stdout_payload, self.stderr_payload


class TestBuildAdapterClass:
    def test_build_adapter_class_creates_custom_assertion_type_and_bool_result(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(args):
    return (
        args["output"] == "needle in haystack"
        and args["value"] == "needle"
        and args["threshold"] == 0.8
    )
""",
            "bool",
        )
        ctx = _make_context()

        assert adapter_cls.type == "custom:budget_guard"

        adapter = adapter_cls(value="needle", threshold=0.8, config={"budget": 0.05})
        assert adapter.value == "needle"
        assert adapter.threshold == 0.8
        assert adapter.config == {"budget": 0.05}

        result = adapter.evaluate("needle in haystack", ctx)

        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "custom:budget_guard"

    def test_adapter_passes_promptfoo_context_aliases_vars_and_config(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "promptfoo_contract",
            """
def get_assert(args):
    ctx = args["context"]
    return (
        ctx["vars"]["topic"] == "launch"
        and ctx["config"]["budget"] == 0.05
        and ctx["prompt"] == "Find the launch blocker."
        and ctx["prompt_hash"] == "prompt-hash-123"
        and ctx["soul_id"] == "soul-1"
        and ctx["soul_version"] == "v7"
        and ctx["block_id"] == "block-a"
        and ctx["block_type"] == "LinearBlock"
        and ctx["cost_usd"] == 0.031
        and ctx["total_tokens"] == 321
        and ctx["latency_ms"] == 245.5
        and ctx["run_id"] == "run-123"
        and ctx["workflow_id"] == "wf-456"
    )
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert result.assertion_type == "custom:promptfoo_contract"

    def test_adapter_validates_grading_result_dict_return(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "rich_result",
            """
def get_assert(args):
    return {
        "passed": args["context"]["vars"]["topic"] == "launch",
        "score": 0.9,
        "reason": "topic matched vars alias",
    }
""",
            "grading_result",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 0.9
        assert result.reason == "topic matched vars alias"
        assert result.assertion_type == "custom:rich_result"

    def test_adapter_wraps_plugin_exception_in_failing_grading_result(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "boom_guard",
            """
def get_assert(args):
    raise RuntimeError("kaboom")
""",
            "bool",
        )
        adapter = adapter_cls()

        result = adapter.evaluate("needle in haystack", _make_context())

        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        assert "Custom assertion 'boom_guard' failed:" in result.reason
        assert "kaboom" in result.reason
        assert result.assertion_type == "custom:boom_guard"

    def test_build_adapter_class_rejects_blocked_imports_before_execution(self):
        _, build_adapter_class = _load_symbols()

        with pytest.raises(ValueError) as exc_info:
            build_adapter_class(
                "unsafe_guard",
                """
import os

def get_assert(args):
    return True
""",
                "bool",
            )

        message = str(exc_info.value)
        assert "os" in message
        assert "not allowed" in message or "allowed list" in message

    def test_adapter_does_not_expose_variables_key_in_context_dict(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "vars_only",
            """
def get_assert(args):
    ctx = args["context"]
    return "variables" not in ctx and ctx["vars"]["severity"] == "high"
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True

    def test_adapter_subprocess_env_is_minimal_and_does_not_forward_api_keys(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "isolated_guard",
            """
def get_assert(args):
    return True
""",
            "bool",
        )
        adapter = adapter_cls()
        captured_env: dict[str, str] | None = None

        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-secret")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic-secret")

        async def fake_create_subprocess_exec(*args, **kwargs):
            nonlocal captured_env
            captured_env = kwargs.get("env")
            return _FakeProc(stdout_payload=json.dumps(True).encode())

        monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert captured_env is not None
        assert "PATH" in captured_env
        assert "OPENAI_API_KEY" not in captured_env
        assert "ANTHROPIC_API_KEY" not in captured_env
