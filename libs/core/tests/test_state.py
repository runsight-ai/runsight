"""
Tests for WorkflowState data model.
"""

from runsight_core.state import WorkflowState
from runsight_core.primitives import Task


def test_workflow_state_initialization():
    """Verify WorkflowState initializes with empty defaults."""
    state = WorkflowState()
    assert state.messages == []
    assert state.shared_memory == {}
    assert state.current_task is None
    assert state.results == {}
    assert state.metadata == {}
    assert state.total_cost_usd == 0.0
    assert state.total_tokens == 0


def test_workflow_state_with_task():
    """Verify WorkflowState accepts Task objects."""
    task = Task(id="t1", instruction="Do work")
    state = WorkflowState(current_task=task)
    assert state.current_task.id == "t1"
    assert state.current_task.instruction == "Do work"


def test_workflow_state_immutability():
    """Verify model_copy creates new instance (addresses tech lead issue #7)."""
    state1 = WorkflowState(results={"a": "output1"})
    state2 = state1.model_copy(update={"results": {"b": "output2"}})

    # state1 unchanged (immutability)
    assert state1.results == {"a": "output1"}
    assert state2.results == {"b": "output2"}
    assert state1 is not state2


def test_workflow_state_model_fields():
    """Verify required fields exist (AC-2)."""
    fields = set(WorkflowState.model_fields.keys())
    required = {
        "messages",
        "shared_memory",
        "current_task",
        "results",
        "metadata",
        "total_cost_usd",
        "total_tokens",
    }
    assert required.issubset(fields)


def test_workflow_state_with_all_fields():
    """Verify WorkflowState can be initialized with all fields."""
    task = Task(id="t1", instruction="Test task")
    state = WorkflowState(
        messages=[{"role": "system", "content": "Hello"}],
        shared_memory={"key": "value"},
        current_task=task,
        results={"block1": "output1"},
        metadata={"blueprint_name": "test_blueprint"},
        total_cost_usd=0.05,
        total_tokens=100,
    )

    assert len(state.messages) == 1
    assert state.messages[0]["role"] == "system"
    assert state.shared_memory["key"] == "value"
    assert state.current_task.id == "t1"
    assert state.results["block1"] == "output1"
    assert state.metadata["blueprint_name"] == "test_blueprint"
    assert state.total_cost_usd == 0.05
    assert state.total_tokens == 100


def test_workflow_state_model_copy_preserves_other_fields():
    """Verify model_copy with update preserves other fields."""
    state1 = WorkflowState(
        results={"a": "output1"}, metadata={"key": "value"}, total_cost_usd=0.01, total_tokens=50
    )
    state2 = state1.model_copy(update={"results": {"a": "output1", "b": "output2"}})

    # Original state unchanged
    assert state1.results == {"a": "output1"}
    assert state1.metadata == {"key": "value"}
    assert state1.total_cost_usd == 0.01
    assert state1.total_tokens == 50

    # New state has updates and preserves metadata
    assert state2.results == {"a": "output1", "b": "output2"}
    assert state2.metadata == {"key": "value"}
    assert state2.total_cost_usd == 0.01
    assert state2.total_tokens == 50
