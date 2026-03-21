"""
Tests for YAML schema models, particularly TaskDef.
"""

import pytest
from pydantic import ValidationError

from runsight_core.blocks.linear import LinearBlockDef
from runsight_core.yaml.schema import (
    TaskDef,
    SoulDef,
    TransitionDef,
    WorkflowDef,
    RunsightWorkflowFile,
)


class TestTaskDef:
    """Tests for TaskDef schema model."""

    def test_taskdef_required_fields(self):
        """TaskDef requires id and instruction fields."""
        with pytest.raises(ValidationError):
            TaskDef(id="test1")  # type: ignore  # missing instruction

        with pytest.raises(ValidationError):
            TaskDef(instruction="Do something")  # type: ignore  # missing id

    def test_taskdef_valid_minimal(self):
        """TaskDef with only required fields (id and instruction) is valid."""
        task = TaskDef(id="task1", instruction="Do something")
        assert task.id == "task1"
        assert task.instruction == "Do something"
        assert task.context is None

    def test_taskdef_valid_with_context(self):
        """TaskDef with all three fields is valid."""
        task = TaskDef(
            id="task2",
            instruction="Review the code",
            context="Here is the code to review",
        )
        assert task.id == "task2"
        assert task.instruction == "Review the code"
        assert task.context == "Here is the code to review"

    def test_taskdef_context_optional(self):
        """TaskDef context field is optional."""
        task1 = TaskDef(id="task3", instruction="Do something", context=None)
        assert task1.context is None

        task2 = TaskDef(id="task4", instruction="Do something")
        assert task2.context is None

    def test_taskdef_fields_are_strings(self):
        """TaskDef id and instruction must be strings."""
        with pytest.raises(ValidationError):
            TaskDef(id=123, instruction="Do something")  # type: ignore

        with pytest.raises(ValidationError):
            TaskDef(id="task5", instruction=456)  # type: ignore

    def test_taskdef_context_must_be_string_or_none(self):
        """TaskDef context must be string or None."""
        with pytest.raises(ValidationError):
            TaskDef(id="task6", instruction="Do something", context=123)  # type: ignore

        task = TaskDef(id="task6", instruction="Do something", context="")
        assert task.context == ""

    def test_taskdef_string_fields_empty_allowed(self):
        """TaskDef allows empty strings (though semantically odd)."""
        task = TaskDef(id="", instruction="")
        assert task.id == ""
        assert task.instruction == ""

    def test_taskdef_from_dict(self):
        """TaskDef can be instantiated from dict."""
        data = {
            "id": "task7",
            "instruction": "Analyze this",
            "context": "Some context",
        }
        task = TaskDef(**data)
        assert task.id == "task7"
        assert task.instruction == "Analyze this"
        assert task.context == "Some context"

    def test_taskdef_model_dump(self):
        """TaskDef can be serialized to dict."""
        task = TaskDef(
            id="task8",
            instruction="Review",
            context="Context here",
        )
        dumped = task.model_dump()
        assert dumped["id"] == "task8"
        assert dumped["instruction"] == "Review"
        assert dumped["context"] == "Context here"

    def test_taskdef_model_dump_excludes_none(self):
        """TaskDef.model_dump(exclude_none=True) excludes None context."""
        task = TaskDef(id="task9", instruction="Do it")
        dumped = task.model_dump(exclude_none=True)
        assert "id" in dumped
        assert "instruction" in dumped
        assert "context" not in dumped


class TestSchemaModelsUnaffected:
    """Verify that existing schema models still work after TaskDef addition."""

    def test_souldef_unchanged(self):
        """SoulDef should work as before."""
        soul = SoulDef(
            id="soul1",
            role="Researcher",
            system_prompt="You are a researcher",
        )
        assert soul.id == "soul1"
        assert soul.role == "Researcher"

    def test_blockdef_unchanged(self):
        """BlockDef discriminated union resolves to per-type model."""
        block = LinearBlockDef(soul_ref="soul1")
        assert block.type == "linear"
        assert block.soul_ref == "soul1"

    def test_transitiondef_unchanged(self):
        """TransitionDef should work as before."""
        transition = TransitionDef(**{"from": "block1", "to": "block2"})
        assert transition.from_ == "block1"
        assert transition.to == "block2"

    def test_workflowdef_unchanged(self):
        """WorkflowDef should work as before."""
        workflow = WorkflowDef(name="test", entry="block1")
        assert workflow.name == "test"
        assert workflow.entry == "block1"

    def test_runsightworkflowfile_unchanged(self):
        """RunsightWorkflowFile should work as before."""
        workflow_def = WorkflowDef(name="test", entry="block1")
        pwf = RunsightWorkflowFile(workflow=workflow_def)
        assert pwf.workflow.name == "test"
        assert pwf.version == "1.0"
