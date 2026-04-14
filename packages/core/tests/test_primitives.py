import pytest
from pydantic import ValidationError
from runsight_core.primitives import Soul, Task


def test_soul_validation():
    soul = Soul(id="test1", kind="soul", name="Coder", role="Coder", system_prompt="Write code.")
    assert soul.id == "test1"
    assert soul.kind == "soul"
    assert soul.name == "Coder"
    assert soul.role == "Coder"
    assert soul.system_prompt == "Write code."
    assert soul.tools is None

    with pytest.raises(ValidationError):
        Soul(kind="soul", name="Coder", role="Coder", system_prompt="Missing id")


def test_task_validation():
    task = Task(id="task1", instruction="Do work")
    assert task.id == "task1"
    assert task.instruction == "Do work"
    assert task.context is None

    task_with_context = Task(id="task2", instruction="Do work", context="Context here")
    assert task_with_context.context == "Context here"
