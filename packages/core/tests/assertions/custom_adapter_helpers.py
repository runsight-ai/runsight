"""Fixture builders for custom assertion adapter tests."""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from typing import Any

from runsight_core.assertions.base import AssertionContext

FIXTURE_OUTPUT = "needle in haystack"


def load_symbols():
    module = importlib.import_module("runsight_core.assertions.custom")
    return module, module._build_adapter_class


def make_context(**overrides: Any) -> AssertionContext:
    defaults = dict(
        output=FIXTURE_OUTPUT,
        prompt="Find the launch blocker.",
        prompt_hash="prompt-hash-fixture",
        soul_id="custom-adapter-soul",
        soul_version="v7",
        block_id="custom-adapter-block",
        block_type="LinearBlock",
        cost_usd=0.031,
        total_tokens=321,
        latency_ms=245.5,
        variables={"topic": "launch", "severity": "high"},
        run_id="custom-adapter-run",
        workflow_id="custom-adapter-workflow",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


def budget_params_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"budget": {"type": "number"}},
        "required": ["budget"],
    }


def nested_params_schema() -> dict[str, Any]:
    return {
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


def bool_plugin_source(return_expression: str = "True") -> str:
    return f"""
def get_assert(output, context):
    return {return_expression}
"""


@dataclass
class FakeProc:
    stdout_payload: bytes
    stderr_payload: bytes = b""
    returncode: int = 0

    async def communicate(self, input: bytes | None = None):
        return self.stdout_payload, self.stderr_payload


@dataclass
class HangingProc:
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
