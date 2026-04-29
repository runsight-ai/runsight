"""Red tests for RUN-796: custom assertion adapter class builder."""

from __future__ import annotations

import asyncio
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


@dataclass
class _HangingProc:
    kill_called: bool = False
    wait_called: bool = False
    returncode: int | None = None

    async def communicate(self, input: bytes | None = None):
        raise asyncio.TimeoutError("timed out after 30s")

    def kill(self):
        self.kill_called = True

    async def wait(self):
        self.wait_called = True
        self.returncode = -9


class TestBuildAdapterClass:
    def test_build_adapter_class_creates_custom_assertion_type_and_bool_result(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(output, context):
    return output == "needle in haystack" and context["vars"]["topic"] == "launch"
""",
            "bool",
        )
        ctx = _make_context()

        assert adapter_cls.type == "custom:budget_guard"

        adapter = adapter_cls(value="ignored", threshold=0.8, config={"budget": 0.05})
        assert adapter.value == "ignored"
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
def get_assert(output, context):
    return (
        output == "needle in haystack"
        and context["vars"]["topic"] == "launch"
        and context["config"]["budget"] == 0.05
        and context["prompt"] == "Find the launch blocker."
        and context["prompt_hash"] == "prompt-hash-123"
        and context["soul_id"] == "soul-1"
        and context["soul_version"] == "v7"
        and context["block_id"] == "block-a"
        and context["block_type"] == "LinearBlock"
        and context["cost_usd"] == 0.031
        and context["total_tokens"] == 321
        and context["latency_ms"] == 245.5
        and context["run_id"] == "run-123"
        and context["workflow_id"] == "wf-456"
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
def get_assert(output, context):
    return {
        "passed": output == "needle in haystack",
        "score": 0.9,
        "reason": f'topic matched {context["vars"]["topic"]}',
    }
""",
            "grading_result",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 0.9
        assert result.reason == "topic matched launch"
        assert result.assertion_type == "custom:rich_result"

    def test_adapter_routes_raw_plugin_result_through_return_validators_table(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        validator_calls: list[tuple[object, str]] = []

        def fake_validator(raw: object, plugin_name: str) -> GradingResult:
            validator_calls.append((raw, plugin_name))
            return GradingResult(
                passed=True,
                score=0.75,
                reason="validated through shared table",
                assertion_type=f"custom:{plugin_name}",
            )

        monkeypatch.setitem(module._RETURN_VALIDATORS, "bool", fake_validator)
        adapter_cls = build_adapter_class(
            "validator_seam",
            """
def get_assert(output, context):
    return {"raw_output": output, "topic": context["vars"]["topic"]}
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert result.score == 0.75
        assert validator_calls == [
            (
                {"raw_output": "needle in haystack", "topic": "launch"},
                "validator_seam",
            )
        ]

    def test_adapter_wraps_plugin_exception_in_failing_grading_result(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "boom_guard",
            """
def get_assert(output, context):
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

def get_assert(output, context):
    return True
""",
                "bool",
            )

        message = str(exc_info.value)
        assert "os" in message
        assert "not allowed" in message or "allowed list" in message

    @pytest.mark.parametrize(
        ("code", "expected_fragment"),
        [
            ("def nope(output, context):\n    return True\n", "get_assert"),
            ("def get_assert(output):\n    return True\n", "get_assert"),
            (
                "def get_assert(args, context, extra):\n    return True\n",
                "get_assert",
            ),
            ("def get_assert(output, context)\n    return True\n", "syntax"),
        ],
    )
    def test_build_adapter_class_rejects_invalid_get_assert_contract_before_execution(
        self,
        code: str,
        expected_fragment: str,
    ):
        _, build_adapter_class = _load_symbols()

        with pytest.raises(ValueError) as exc_info:
            build_adapter_class("bad_contract", code, "bool")

        message = str(exc_info.value).lower()
        assert expected_fragment in message

    def test_adapter_does_not_expose_variables_key_in_context_dict(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "vars_only",
            """
def get_assert(output, context):
    return "variables" not in context and context["vars"]["severity"] == "high"
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True

    def test_adapter_passes_non_dict_config_through_to_plugin_context(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "raw_config_passthrough",
            """
def get_assert(output, context):
    return context["config"] == "raw-config-token"
""",
            "bool",
        )
        adapter = adapter_cls(config="raw-config-token")

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True

    def test_adapter_subprocess_env_is_minimal_and_does_not_forward_api_keys(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "isolated_guard",
            """
def get_assert(output, context):
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

    @pytest.mark.asyncio
    async def test_adapter_evaluate_succeeds_inside_running_event_loop(self):
        _, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "loop_safe_guard",
            """
def get_assert(output, context):
    return output == "needle in haystack" and context["vars"]["topic"] == "launch"
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert result.assertion_type == "custom:loop_safe_guard"

    def test_adapter_timeout_kills_process_waits_and_returns_failing_result(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        adapter_cls = build_adapter_class(
            "timeout_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls()
        proc = _HangingProc()

        async def fake_create_subprocess_exec(*args, **kwargs):
            return proc

        monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        assert "timeout_guard" in result.reason
        assert "30" in result.reason or "timed out" in result.reason
        assert proc.kill_called is True
        assert proc.wait_called is True


class TestAdapterParamSchemaValidation:
    def test_valid_config_against_declared_params_schema_runs_plugin_and_passes(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(
            module,
            "_PARAM_SCHEMAS",
            {
                "budget_guard": {
                    "type": "object",
                    "properties": {"budget": {"type": "number"}},
                    "required": ["budget"],
                }
            },
            raising=False,
        )
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": 0.05})

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert plugin_calls == [
            {
                "vars": {"topic": "launch", "severity": "high"},
                "config": {"budget": 0.05},
                "prompt": "Find the launch blocker.",
                "prompt_hash": "prompt-hash-123",
                "soul_id": "soul-1",
                "soul_version": "v7",
                "block_id": "block-a",
                "block_type": "LinearBlock",
                "cost_usd": 0.031,
                "total_tokens": 321,
                "latency_ms": 245.5,
                "run_id": "run-123",
                "workflow_id": "wf-456",
            }
        ]

    def test_missing_required_field_returns_failing_grading_result_and_skips_plugin(
        self, monkeypatch
    ):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(
            module,
            "_PARAM_SCHEMAS",
            {
                "budget_guard": {
                    "type": "object",
                    "properties": {"budget": {"type": "number"}},
                    "required": ["budget"],
                }
            },
            raising=False,
        )
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config={})

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is False
        assert result.reason.startswith("Config validation failed:")
        assert plugin_calls == []

    def test_wrong_type_returns_failing_grading_result_and_skips_plugin(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(
            module,
            "_PARAM_SCHEMAS",
            {
                "budget_guard": {
                    "type": "object",
                    "properties": {"budget": {"type": "number"}},
                    "required": ["budget"],
                }
            },
            raising=False,
        )
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config={"budget": "expensive"})

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is False
        assert result.reason.startswith("Config validation failed:")
        assert plugin_calls == []

    def test_no_params_schema_skips_validation_and_runs_plugin(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(module, "_PARAM_SCHEMAS", {}, raising=False)
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "no_schema_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config=None)

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is True
        assert len(plugin_calls) == 1

    def test_config_none_with_required_params_returns_failing_grading_result(self, monkeypatch):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(
            module,
            "_PARAM_SCHEMAS",
            {
                "budget_guard": {
                    "type": "object",
                    "properties": {"budget": {"type": "number"}},
                    "required": ["budget"],
                }
            },
            raising=False,
        )
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "budget_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config=None)

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is False
        assert result.reason.startswith("Config validation failed:")
        assert plugin_calls == []

    def test_nested_schema_validation_returns_failing_grading_result_and_skips_plugin(
        self, monkeypatch
    ):
        module, build_adapter_class = _load_symbols()
        monkeypatch.setattr(
            module,
            "_PARAM_SCHEMAS",
            {
                "nested_guard": {
                    "type": "object",
                    "properties": {
                        "limits": {
                            "type": "object",
                            "properties": {"budget": {"type": "number"}},
                            "required": ["budget"],
                        }
                    },
                    "required": ["limits"],
                }
            },
            raising=False,
        )
        plugin_calls: list[dict[str, Any]] = []
        adapter_cls = build_adapter_class(
            "nested_guard",
            """
def get_assert(output, context):
    return True
""",
            "bool",
        )
        adapter = adapter_cls(config={"limits": {"budget": "too-high"}})

        def fake_run_plugin_sync(harness, output, plugin_context, *, timeout_seconds=30):
            plugin_calls.append(plugin_context)
            return True

        monkeypatch.setattr(module, "_run_plugin_sync", fake_run_plugin_sync)

        result = adapter.evaluate("needle in haystack", _make_context())

        assert result.passed is False
        assert result.reason.startswith("Config validation failed:")
        assert plugin_calls == []
