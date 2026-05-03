"""PromptEnvelope model exports and field contracts."""

from __future__ import annotations

import pytest


def test_prompt_envelope_is_exported_and_task_envelope_is_not() -> None:
    import runsight_core.isolation as isolation
    from pydantic import BaseModel
    from runsight_core.isolation import PromptEnvelope

    assert "PromptEnvelope" in isolation.__all__
    assert "TaskEnvelope" not in isolation.__all__
    assert issubclass(PromptEnvelope, BaseModel)
    with pytest.raises((ImportError, AttributeError)):
        from runsight_core.isolation import TaskEnvelope  # noqa: F401


def test_context_envelope_uses_prompt_field_and_rejects_task_field() -> None:
    from runsight_core.isolation import ContextEnvelope, PromptEnvelope, SoulEnvelope

    soul = SoulEnvelope(
        id="worker-soul",
        role="worker",
        system_prompt="You are helpful.",
        model_name="gpt-4o-mini",
        max_tool_iterations=3,
    )
    prompt = PromptEnvelope(id="pe-42", instruction="Summarize this.", context={"doc": "abc"})

    env = ContextEnvelope(
        block_id="worker-block",
        block_type="linear",
        block_config={},
        soul=soul,
        tools=[],
        prompt=prompt,
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=10,
        max_output_bytes=512,
    )

    assert env.prompt is prompt
    assert env.prompt.instruction == "Summarize this."
    assert not hasattr(env, "task")
    with pytest.raises(Exception):
        ContextEnvelope(
            block_id="worker-block",
            block_type="linear",
            block_config={},
            soul=soul,
            tools=[],
            task=prompt,
            scoped_results={},
            scoped_shared_memory={},
            conversation_history=[],
            timeout_seconds=10,
            max_output_bytes=512,
        )


def test_delegate_artifact_uses_prompt_field_and_round_trips_json() -> None:
    from runsight_core.isolation import DelegateArtifact

    original = DelegateArtifact(prompt="analyze the report")
    restored = DelegateArtifact.model_validate_json(original.model_dump_json())

    assert restored.prompt == "analyze the report"
    assert not hasattr(restored, "task")
    with pytest.raises(Exception):
        DelegateArtifact(task="old field")
