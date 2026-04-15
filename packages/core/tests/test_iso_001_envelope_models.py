"""
Failing tests for RUN-392: ISO-001 — ContextEnvelope + ResultEnvelope + HeartbeatMessage.

Tests cover:
- All models are Pydantic BaseModel with model_validate_json support (AC1)
- ContextEnvelope JSON round-trip (AC2)
- ResultEnvelope JSON round-trip (AC3)
- HeartbeatMessage serializes to single JSON line (AC4)
- ContextEnvelope has ALL required fields (AC5)
- ResultEnvelope has ALL required fields (AC6)
- HeartbeatMessage has ALL required fields (AC7)
- Sub-models: SoulEnvelope, ToolDefEnvelope, PromptEnvelope, DelegateArtifact
"""

import json
from datetime import datetime

import pytest

# ==============================================================================
# AC1: All models are Pydantic BaseModel with model_validate_json
# ==============================================================================


class TestModelsArePydanticBaseModel:
    """All envelope models must be Pydantic BaseModel subclasses."""

    def test_context_envelope_is_base_model(self):
        """ContextEnvelope is a Pydantic BaseModel."""
        from pydantic import BaseModel
        from runsight_core.isolation import ContextEnvelope

        assert issubclass(ContextEnvelope, BaseModel)

    def test_result_envelope_is_base_model(self):
        """ResultEnvelope is a Pydantic BaseModel."""
        from pydantic import BaseModel
        from runsight_core.isolation import ResultEnvelope

        assert issubclass(ResultEnvelope, BaseModel)

    def test_heartbeat_message_is_base_model(self):
        """HeartbeatMessage is a Pydantic BaseModel."""
        from pydantic import BaseModel
        from runsight_core.isolation import HeartbeatMessage

        assert issubclass(HeartbeatMessage, BaseModel)

    def test_context_envelope_supports_model_validate_json(self):
        """ContextEnvelope has model_validate_json (Pydantic v2 method)."""
        from runsight_core.isolation import ContextEnvelope

        assert callable(getattr(ContextEnvelope, "model_validate_json", None))

    def test_result_envelope_supports_model_validate_json(self):
        """ResultEnvelope has model_validate_json (Pydantic v2 method)."""
        from runsight_core.isolation import ResultEnvelope

        assert callable(getattr(ResultEnvelope, "model_validate_json", None))

    def test_heartbeat_message_supports_model_validate_json(self):
        """HeartbeatMessage has model_validate_json (Pydantic v2 method)."""
        from runsight_core.isolation import HeartbeatMessage

        assert callable(getattr(HeartbeatMessage, "model_validate_json", None))


# ==============================================================================
# AC5: ContextEnvelope fields
# ==============================================================================


class TestContextEnvelopeFields:
    """ContextEnvelope must have all specified fields."""

    def _make_minimal_context_envelope(self):
        """Build a minimal ContextEnvelope with all required fields populated."""
        from runsight_core.isolation import (
            ContextEnvelope,
            PromptEnvelope,
            SoulEnvelope,
            ToolDefEnvelope,
        )

        soul = SoulEnvelope(
            id="soul-1",
            role="assistant",
            system_prompt="You are helpful.",
            model_name="gpt-4",
            max_tool_iterations=5,
        )
        tool = ToolDefEnvelope(
            source="runsight/file-io",
            config={"base_dir": "/tmp/workflow"},
            exits=["done", "error"],
            name="file_io",
            description="Read and write workflow files.",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            tool_type="builtin",
        )
        prompt = PromptEnvelope(
            id="task-1",
            instruction="Do the thing.",
            context={"input": "data"},
        )
        return ContextEnvelope(
            block_id="block-1",
            block_type="llm",
            block_config={"temperature": 0.7},
            soul=soul,
            tools=[tool],
            prompt=prompt,
            scoped_results={"prev_block": {"output": "hello"}},
            scoped_shared_memory={"key1": "value1"},
            conversation_history=[{"role": "user", "content": "hi"}],
            timeout_seconds=30,
            max_output_bytes=1024,
        )

    def test_context_envelope_has_block_id(self):
        """ContextEnvelope has block_id field."""
        env = self._make_minimal_context_envelope()
        assert env.block_id == "block-1"

    def test_context_envelope_has_block_type(self):
        """ContextEnvelope has block_type field."""
        env = self._make_minimal_context_envelope()
        assert env.block_type == "llm"

    def test_context_envelope_has_block_config(self):
        """ContextEnvelope has block_config field."""
        env = self._make_minimal_context_envelope()
        assert env.block_config == {"temperature": 0.7}

    def test_context_envelope_has_soul_envelope(self):
        """ContextEnvelope has a SoulEnvelope."""
        from runsight_core.isolation import SoulEnvelope

        env = self._make_minimal_context_envelope()
        assert isinstance(env.soul, SoulEnvelope)
        assert env.soul.id == "soul-1"
        assert env.soul.role == "assistant"
        assert env.soul.system_prompt == "You are helpful."
        assert env.soul.model_name == "gpt-4"
        assert env.soul.max_tool_iterations == 5

    def test_context_envelope_has_tool_def_envelopes(self):
        """ContextEnvelope has a list of ToolDefEnvelope."""
        from runsight_core.isolation import ToolDefEnvelope

        env = self._make_minimal_context_envelope()
        assert isinstance(env.tools, list)
        assert len(env.tools) == 1
        assert isinstance(env.tools[0], ToolDefEnvelope)
        assert env.tools[0].source == "runsight/file-io"
        assert env.tools[0].config == {"base_dir": "/tmp/workflow"}
        assert env.tools[0].exits == ["done", "error"]
        assert env.tools[0].name == "file_io"
        assert env.tools[0].description == "Read and write workflow files."
        assert env.tools[0].parameters == {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
        assert env.tools[0].tool_type == "builtin"

    def test_context_envelope_has_task_envelope(self):
        """ContextEnvelope has a PromptEnvelope."""
        from runsight_core.isolation import PromptEnvelope

        env = self._make_minimal_context_envelope()
        assert isinstance(env.prompt, PromptEnvelope)
        assert env.prompt.id == "task-1"
        assert env.prompt.instruction == "Do the thing."
        assert env.prompt.context == {"input": "data"}

    def test_context_envelope_has_scoped_results(self):
        """ContextEnvelope has scoped_results dict."""
        env = self._make_minimal_context_envelope()
        assert env.scoped_results == {"prev_block": {"output": "hello"}}

    def test_context_envelope_has_scoped_shared_memory(self):
        """ContextEnvelope has scoped_shared_memory dict."""
        env = self._make_minimal_context_envelope()
        assert env.scoped_shared_memory == {"key1": "value1"}

    def test_context_envelope_has_conversation_history(self):
        """ContextEnvelope has conversation_history list."""
        env = self._make_minimal_context_envelope()
        assert env.conversation_history == [{"role": "user", "content": "hi"}]

    def test_context_envelope_has_timeout_seconds(self):
        """ContextEnvelope has timeout_seconds."""
        env = self._make_minimal_context_envelope()
        assert env.timeout_seconds == 30

    def test_context_envelope_has_max_output_bytes(self):
        """ContextEnvelope has max_output_bytes."""
        env = self._make_minimal_context_envelope()
        assert env.max_output_bytes == 1024


# ==============================================================================
# AC2: ContextEnvelope JSON round-trip
# ==============================================================================


class TestContextEnvelopeRoundTrip:
    """ContextEnvelope must survive JSON serialization and deserialization."""

    def test_context_envelope_round_trips_through_json(self):
        """ContextEnvelope -> JSON string -> ContextEnvelope preserves all data."""
        from runsight_core.isolation import (
            ContextEnvelope,
            PromptEnvelope,
            SoulEnvelope,
            ToolDefEnvelope,
        )

        original = ContextEnvelope(
            block_id="b1",
            block_type="llm",
            block_config={"temp": 0.5},
            soul=SoulEnvelope(
                id="s1",
                role="agent",
                system_prompt="prompt",
                model_name="gpt-4",
                max_tool_iterations=3,
            ),
            tools=[
                ToolDefEnvelope(
                    source="custom/profile_lookup",
                    config={"timeout_seconds": 15},
                    exits=["ok"],
                    name="profile_lookup",
                    description="Fetch a profile by id.",
                    parameters={"type": "object", "properties": {"user_id": {"type": "string"}}},
                    tool_type="http",
                ),
            ],
            prompt=PromptEnvelope(id="t1", instruction="run", context={}),
            scoped_results={"x": {"out": "val"}},
            scoped_shared_memory={"mem": 42},
            conversation_history=[{"role": "assistant", "content": "hey"}],
            timeout_seconds=60,
            max_output_bytes=2048,
        )

        json_str = original.model_dump_json()
        restored = ContextEnvelope.model_validate_json(json_str)

        assert restored.block_id == original.block_id
        assert restored.block_type == original.block_type
        assert restored.block_config == original.block_config
        assert restored.soul.id == original.soul.id
        assert restored.soul.model_name == original.soul.model_name
        assert len(restored.tools) == len(original.tools)
        assert restored.tools[0].source == original.tools[0].source
        assert restored.tools[0].config == original.tools[0].config
        assert restored.tools[0].exits == original.tools[0].exits
        assert restored.tools[0].name == original.tools[0].name
        assert restored.tools[0].description == original.tools[0].description
        assert restored.tools[0].parameters == original.tools[0].parameters
        assert restored.tools[0].tool_type == original.tools[0].tool_type
        assert restored.prompt.id == original.prompt.id
        assert restored.scoped_results == original.scoped_results
        assert restored.scoped_shared_memory == original.scoped_shared_memory
        assert restored.conversation_history == original.conversation_history
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.max_output_bytes == original.max_output_bytes

    def test_context_envelope_model_dump_is_json_serializable(self):
        """ContextEnvelope.model_dump() produces a stdlib-json-serializable dict."""
        from runsight_core.isolation import (
            ContextEnvelope,
            PromptEnvelope,
            SoulEnvelope,
        )

        env = ContextEnvelope(
            block_id="b1",
            block_type="code",
            block_config={},
            soul=SoulEnvelope(
                id="s1",
                role="worker",
                system_prompt="go",
                model_name="claude-3",
                max_tool_iterations=1,
            ),
            tools=[],
            prompt=PromptEnvelope(id="t1", instruction="exec", context={}),
            scoped_results={},
            scoped_shared_memory={},
            conversation_history=[],
            timeout_seconds=10,
            max_output_bytes=512,
        )

        dumped = env.model_dump()
        assert isinstance(dumped, dict)
        json_str = json.dumps(dumped)
        assert isinstance(json_str, str)


# ==============================================================================
# AC6: ResultEnvelope fields
# ==============================================================================


class TestResultEnvelopeFields:
    """ResultEnvelope must have all specified fields."""

    def _make_result_envelope(self):
        from runsight_core.isolation import DelegateArtifact, ResultEnvelope

        return ResultEnvelope(
            block_id="block-1",
            output="result text",
            exit_handle="done",
            cost_usd=0.0042,
            total_tokens=150,
            tool_calls_made=2,
            delegate_artifacts={
                "port_a": DelegateArtifact(prompt="summarize doc"),
            },
            conversation_history=[{"role": "assistant", "content": "done"}],
            error=None,
            error_type=None,
        )

    def test_result_envelope_has_block_id(self):
        env = self._make_result_envelope()
        assert env.block_id == "block-1"

    def test_result_envelope_has_output(self):
        env = self._make_result_envelope()
        assert env.output == "result text"

    def test_result_envelope_has_exit_handle(self):
        env = self._make_result_envelope()
        assert env.exit_handle == "done"

    def test_result_envelope_has_cost_usd(self):
        env = self._make_result_envelope()
        assert env.cost_usd == pytest.approx(0.0042)

    def test_result_envelope_has_total_tokens(self):
        env = self._make_result_envelope()
        assert env.total_tokens == 150

    def test_result_envelope_has_tool_calls_made(self):
        env = self._make_result_envelope()
        assert env.tool_calls_made == 2

    def test_result_envelope_has_delegate_artifacts(self):
        from runsight_core.isolation import DelegateArtifact

        env = self._make_result_envelope()
        assert "port_a" in env.delegate_artifacts
        assert isinstance(env.delegate_artifacts["port_a"], DelegateArtifact)
        assert env.delegate_artifacts["port_a"].prompt == "summarize doc"

    def test_result_envelope_has_conversation_history(self):
        env = self._make_result_envelope()
        assert env.conversation_history == [{"role": "assistant", "content": "done"}]

    def test_result_envelope_has_error_fields(self):
        env = self._make_result_envelope()
        assert env.error is None
        assert env.error_type is None

    def test_result_envelope_error_fields_populated_on_failure(self):
        """ResultEnvelope can represent a failure with error and error_type."""
        from runsight_core.isolation import ResultEnvelope

        env = ResultEnvelope(
            block_id="block-2",
            output=None,
            exit_handle="error",
            cost_usd=0.001,
            total_tokens=10,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error="LLM timeout after 30s",
            error_type="TimeoutError",
        )
        assert env.error == "LLM timeout after 30s"
        assert env.error_type == "TimeoutError"


# ==============================================================================
# AC3: ResultEnvelope JSON round-trip
# ==============================================================================


class TestResultEnvelopeRoundTrip:
    """ResultEnvelope must survive JSON serialization and deserialization."""

    def test_result_envelope_round_trips_through_json(self):
        from runsight_core.isolation import DelegateArtifact, ResultEnvelope

        original = ResultEnvelope(
            block_id="b1",
            output="done",
            exit_handle="success",
            cost_usd=0.01,
            total_tokens=200,
            tool_calls_made=3,
            delegate_artifacts={
                "main": DelegateArtifact(prompt="write report"),
            },
            conversation_history=[{"role": "user", "content": "go"}],
            error=None,
            error_type=None,
        )

        json_str = original.model_dump_json()
        restored = ResultEnvelope.model_validate_json(json_str)

        assert restored.block_id == original.block_id
        assert restored.output == original.output
        assert restored.exit_handle == original.exit_handle
        assert restored.cost_usd == pytest.approx(original.cost_usd)
        assert restored.total_tokens == original.total_tokens
        assert restored.tool_calls_made == original.tool_calls_made
        assert restored.delegate_artifacts["main"].prompt == "write report"
        assert restored.conversation_history == original.conversation_history
        assert restored.error is None
        assert restored.error_type is None


# ==============================================================================
# AC7: HeartbeatMessage fields
# ==============================================================================


class TestHeartbeatMessageFields:
    """HeartbeatMessage must have all specified fields."""

    def test_heartbeat_has_sequence_number(self):
        from runsight_core.isolation import HeartbeatMessage

        hb = HeartbeatMessage(
            heartbeat=1,
            phase="init",
            detail="loading model",
            timestamp=datetime(2026, 3, 28, 12, 0, 0),
        )
        assert hb.heartbeat == 1

    def test_heartbeat_has_phase(self):
        from runsight_core.isolation import HeartbeatMessage

        hb = HeartbeatMessage(
            heartbeat=2,
            phase="executing",
            detail="calling tool",
            timestamp=datetime(2026, 3, 28, 12, 0, 1),
        )
        assert hb.phase == "executing"

    def test_heartbeat_has_detail(self):
        from runsight_core.isolation import HeartbeatMessage

        hb = HeartbeatMessage(
            heartbeat=3,
            phase="done",
            detail="finished",
            timestamp=datetime(2026, 3, 28, 12, 0, 2),
        )
        assert hb.detail == "finished"

    def test_heartbeat_has_timestamp(self):
        from runsight_core.isolation import HeartbeatMessage

        ts = datetime(2026, 3, 28, 12, 0, 0)
        hb = HeartbeatMessage(
            heartbeat=1,
            phase="init",
            detail="start",
            timestamp=ts,
        )
        assert hb.timestamp == ts


# ==============================================================================
# AC4: HeartbeatMessage serializes to single JSON line
# ==============================================================================


class TestHeartbeatMessageSingleLine:
    """HeartbeatMessage must serialize to a single JSON line (for stderr IPC)."""

    def test_heartbeat_serializes_to_single_line(self):
        from runsight_core.isolation import HeartbeatMessage

        hb = HeartbeatMessage(
            heartbeat=1,
            phase="running",
            detail="step 1 of 3",
            timestamp=datetime(2026, 3, 28, 12, 0, 0),
        )
        json_str = hb.model_dump_json()
        assert "\n" not in json_str, "HeartbeatMessage JSON must be a single line"

    def test_heartbeat_round_trips_through_json(self):
        from runsight_core.isolation import HeartbeatMessage

        original = HeartbeatMessage(
            heartbeat=5,
            phase="tool_call",
            detail="calling http_get",
            timestamp=datetime(2026, 3, 28, 12, 5, 30),
        )
        json_str = original.model_dump_json()
        restored = HeartbeatMessage.model_validate_json(json_str)

        assert restored.heartbeat == original.heartbeat
        assert restored.phase == original.phase
        assert restored.detail == original.detail

    def test_heartbeat_parseable_from_raw_json_line(self):
        """HeartbeatMessage can be parsed from a raw JSON string (simulating stderr read)."""
        from runsight_core.isolation import HeartbeatMessage

        raw_line = json.dumps(
            {
                "heartbeat": 10,
                "phase": "complete",
                "detail": "all done",
                "timestamp": "2026-03-28T12:00:00",
            }
        )
        hb = HeartbeatMessage.model_validate_json(raw_line)
        assert hb.heartbeat == 10
        assert hb.phase == "complete"
        assert hb.detail == "all done"


# ==============================================================================
# Sub-model tests: DelegateArtifact
# ==============================================================================


class TestDelegateArtifact:
    """DelegateArtifact model tests."""

    def test_delegate_artifact_has_task(self):
        from runsight_core.isolation import DelegateArtifact

        da = DelegateArtifact(prompt="summarize the document")
        assert da.prompt == "summarize the document"

    def test_delegate_artifact_is_base_model(self):
        from pydantic import BaseModel
        from runsight_core.isolation import DelegateArtifact

        assert issubclass(DelegateArtifact, BaseModel)
