"""Tests for entity extra field configuration.

SoulEntity and WorkflowEntity preserve extra fields. TaskEntity and StepEntity
still use extra="ignore" — unknown fields are silently dropped.
"""

from runsight_api.domain.value_objects import (
    SoulEntity,
    StepEntity,
    TaskEntity,
    WorkflowEntity,
)

# ── SoulEntity ──────────────────────────────────────────────────────


class TestSoulEntityPreservesExtraFields:
    def test_unknown_field_is_preserved(self):
        soul = SoulEntity(id="s1", role="Alpha", bogus_field="oops")
        assert soul.bogus_field == "oops"

    def test_typo_field_is_preserved(self):
        soul = SoulEntity(id="s1", naem="typo")
        assert soul.naem == "typo"
        assert soul.role is None  # default kept

    def test_known_fields_work(self):
        soul = SoulEntity(
            id="s1",
            role="Alpha",
            system_prompt="Prompt",
            model_name="gpt-4o",
            max_tool_iterations=7,
        )
        assert soul.id == "s1"
        assert soul.role == "Alpha"
        assert soul.system_prompt == "Prompt"
        assert soul.model_name == "gpt-4o"
        assert soul.max_tool_iterations == 7

    def test_declared_runtime_fields_are_preserved(self):
        soul = SoulEntity(
            id="s1",
            name="Alpha",
            role="Researcher",
            system_prompt="You analyze things.",
            model_name="gpt-4o",
            models=["gpt-4o", "gpt-4o-mini"],
            tools=["web_search"],
            max_tool_iterations=3,
        )

        assert soul.role == "Researcher"
        assert soul.system_prompt == "You analyze things."
        assert soul.model_name == "gpt-4o"
        assert soul.models == ["gpt-4o", "gpt-4o-mini"]
        assert soul.tools == ["web_search"]
        assert soul.max_tool_iterations == 3


# ── TaskEntity ──────────────────────────────────────────────────────


class TestTaskEntityIgnoresExtraFields:
    def test_unknown_field_is_ignored(self):
        task = TaskEntity(id="t1", name="Build", extra_stuff=42)
        assert not hasattr(task, "extra_stuff")

    def test_typo_field_is_not_stored(self):
        task = TaskEntity(id="t1", naem="typo")
        assert not hasattr(task, "naem")
        assert task.name is None

    def test_known_fields_work(self):
        task = TaskEntity(id="t1", name="Build")
        assert task.id == "t1"
        assert task.name == "Build"


# ── StepEntity ──────────────────────────────────────────────────────


class TestStepEntityIgnoresExtraFields:
    def test_unknown_field_is_ignored(self):
        step = StepEntity(id="st1", name="Compile", random_key="val")
        assert not hasattr(step, "random_key")

    def test_typo_field_is_not_stored(self):
        step = StepEntity(id="st1", naem="typo")
        assert not hasattr(step, "naem")
        assert step.name is None

    def test_known_fields_work(self):
        step = StepEntity(id="st1", name="Compile")
        assert step.id == "st1"
        assert step.name == "Compile"


# ── WorkflowEntity (extra="allow" preserved) ───────────────────────


class TestWorkflowEntityPreservesExtraFields:
    def test_unknown_field_is_preserved(self):
        wf = WorkflowEntity(id="wf1", name="Pipeline", custom_meta="keep-me")
        assert hasattr(wf, "custom_meta")
        assert wf.custom_meta == "keep-me"

    def test_known_fields_work(self):
        wf = WorkflowEntity(id="wf1", name="Pipeline")
        assert wf.id == "wf1"
        assert wf.name == "Pipeline"
