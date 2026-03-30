"""Tests for entity extra field configuration (RUN-321).

SoulEntity, TaskEntity, StepEntity should use extra="ignore" — unknown fields
are silently dropped.  WorkflowEntity should keep extra="allow" — unknown
fields are preserved.
"""

from runsight_api.domain.value_objects import (
    SoulEntity,
    StepEntity,
    TaskEntity,
    WorkflowEntity,
)

# ── SoulEntity ──────────────────────────────────────────────────────


class TestSoulEntityIgnoresExtraFields:
    def test_unknown_field_is_ignored(self):
        soul = SoulEntity(id="s1", name="Alpha", bogus_field="oops")
        assert not hasattr(soul, "bogus_field")

    def test_typo_field_is_not_stored(self):
        soul = SoulEntity(id="s1", naem="typo")
        assert not hasattr(soul, "naem")
        assert soul.name is None  # default kept

    def test_known_fields_work(self):
        soul = SoulEntity(id="s1", name="Alpha")
        assert soul.id == "s1"
        assert soul.name == "Alpha"

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
