"""Smoke coverage for isolation envelope serialization contracts."""

from __future__ import annotations

import json
from datetime import datetime


def test_context_envelope_round_trips_nested_runtime_payload() -> None:
    from runsight_core.isolation import (
        ContextEnvelope,
        PromptEnvelope,
        SoulEnvelope,
        ToolDefEnvelope,
    )

    original = ContextEnvelope(
        block_id="envelope-block",
        block_type="llm",
        block_config={"temperature": 0.2},
        soul=SoulEnvelope(
            id="researcher",
            role="Researcher",
            system_prompt="Research carefully.",
            model_name="gpt-4o-mini",
            provider="openai",
            max_tool_iterations=2,
        ),
        tools=[
            ToolDefEnvelope(
                source="custom/profile_lookup",
                config={"timeout_seconds": 5},
                exits=["done"],
                name="profile_lookup",
                description="Lookup a profile.",
                parameters={"type": "object", "properties": {"user_id": {"type": "string"}}},
                tool_type="custom",
            )
        ],
        prompt=PromptEnvelope(
            id="prompt-1",
            instruction="Summarize the profile.",
            context={"format": "brief"},
        ),
        inputs={"user_id": "u-123"},
        scoped_workflow_inputs={"topic": "profiles"},
        scoped_results={"load": {"output": "raw profile"}},
        scoped_shared_memory={"trace_id": "trace-1"},
        scoped_metadata={"run_id": "run-1"},
        conversation_history=[{"role": "user", "content": "go"}],
        timeout_seconds=30,
        max_output_bytes=4096,
    )

    restored = ContextEnvelope.model_validate_json(original.model_dump_json())

    assert restored.block_id == "envelope-block"
    assert restored.soul.id == "researcher"
    assert restored.tools[0].name == "profile_lookup"
    assert restored.prompt.context == {"format": "brief"}
    assert restored.inputs == {"user_id": "u-123"}
    assert restored.scoped_workflow_inputs == {"topic": "profiles"}
    assert restored.scoped_results == {"load": {"output": "raw profile"}}
    assert restored.scoped_metadata == {"run_id": "run-1"}


def test_result_envelope_round_trips_delegate_artifacts_and_failure_fields() -> None:
    from runsight_core.isolation import DelegateArtifact, ResultEnvelope

    original = ResultEnvelope(
        block_id="tool-block",
        output=None,
        exit_handle="error",
        cost_usd=0.01,
        total_tokens=12,
        tool_calls_made=1,
        delegate_artifacts={"summary": DelegateArtifact(prompt="summarize profile")},
        conversation_history=[{"role": "assistant", "content": "failed"}],
        error="timeout",
        error_type="TimeoutError",
    )

    restored = ResultEnvelope.model_validate_json(original.model_dump_json())

    assert restored.exit_handle == "error"
    assert restored.delegate_artifacts["summary"].prompt == "summarize profile"
    assert restored.error == "timeout"
    assert restored.error_type == "TimeoutError"


def test_heartbeat_message_is_single_line_json() -> None:
    from runsight_core.isolation import HeartbeatMessage

    original = HeartbeatMessage(
        heartbeat=3,
        phase="running",
        detail="calling tool",
        timestamp=datetime(2026, 3, 28, 12, 0, 0),
    )

    raw_line = original.model_dump_json()
    restored = HeartbeatMessage.model_validate_json(raw_line)

    assert "\n" not in raw_line
    assert json.loads(raw_line)["phase"] == "running"
    assert restored.detail == "calling tool"
