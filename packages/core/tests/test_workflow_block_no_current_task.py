"""
RUN-877: WorkflowBlock — remove current_task from dotted path resolution.

These tests are RED (failing) until _resolve_dotted and _write_dotted are
updated to reject the "current_task" prefix and list only
results / shared_memory / metadata as valid prefixes.
"""

import pytest
from runsight_core import WorkflowBlock
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_block(block_id: str = "wf_block") -> WorkflowBlock:
    """Return a minimal WorkflowBlock (child_workflow never executed)."""
    from unittest.mock import AsyncMock

    mock_child = AsyncMock()
    mock_child.name = "child_wf"
    return WorkflowBlock(
        block_id=block_id,
        child_workflow=mock_child,
        inputs={},
        outputs={},
        max_depth=10,
    )


def _make_state(**kwargs) -> WorkflowState:
    return WorkflowState(
        shared_memory=kwargs.get("shared_memory", {"key": "val"}),
        results=kwargs.get("results", {"step1": BlockResult(output="out")}),
        metadata=kwargs.get("metadata", {"run_id": "abc"}),
        # current_task is Optional[Task]; leave None — the path strings are
        # what the tests exercise, not the value stored in the field.
        current_task=None,
    )


# ---------------------------------------------------------------------------
# _resolve_dotted — current_task must raise ValueError
# ---------------------------------------------------------------------------


def test_resolve_dotted_current_task_raises():
    """_resolve_dotted must raise ValueError for 'current_task' prefix."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError):
        block._resolve_dotted(state, "current_task")


def test_resolve_dotted_current_task_dotted_raises_with_deprecation():
    """_resolve_dotted must raise ValueError for 'current_task.instruction' with deprecation hint."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError, match=r"(?i)deprecat|use results\.\*|use shared_memory\.\*"):
        block._resolve_dotted(state, "current_task.instruction")


def test_resolve_dotted_current_task_error_mentions_deprecated():
    """Error for 'current_task' path must mention deprecation guidance."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError, match=r"(?i)deprecat|use results\.\*|use shared_memory\.\*"):
        block._resolve_dotted(state, "current_task")


def test_resolve_dotted_error_does_not_list_current_task_as_valid():
    """Error message for an unknown prefix must NOT list 'current_task' as valid."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError) as exc_info:
        block._resolve_dotted(state, "bogus_prefix.field")

    assert "current_task" not in exc_info.value.args[0]


# ---------------------------------------------------------------------------
# _write_dotted — current_task must raise ValueError
# ---------------------------------------------------------------------------


def test_write_dotted_current_task_raises():
    """_write_dotted must raise ValueError for 'current_task' prefix."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError):
        block._write_dotted(state, "current_task", "new value")


def test_write_dotted_current_task_error_mentions_deprecated():
    """Error for 'current_task' write must mention deprecation guidance."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError, match=r"(?i)deprecat|use results\.\*|use shared_memory\.\*"):
        block._write_dotted(state, "current_task", "new value")


def test_write_dotted_error_does_not_list_current_task_as_valid():
    """Error message for an unknown prefix in write must NOT list 'current_task'."""
    block = _make_block()
    state = _make_state()

    with pytest.raises(ValueError) as exc_info:
        block._write_dotted(state, "bogus_prefix.field", "v")

    assert "current_task" not in exc_info.value.args[0]


# ---------------------------------------------------------------------------
# _resolve_dotted — valid prefixes still work
# ---------------------------------------------------------------------------


def test_resolve_dotted_results_still_works():
    """_resolve_dotted must still resolve 'results.*' paths."""
    block = _make_block()
    state = _make_state(results={"step1": BlockResult(output="hello")})

    value = block._resolve_dotted(state, "results.step1")
    assert isinstance(value, BlockResult)
    assert value.output == "hello"


def test_resolve_dotted_shared_memory_still_works():
    """_resolve_dotted must still resolve 'shared_memory.*' paths."""
    block = _make_block()
    state = _make_state(shared_memory={"topic": "AI"})

    assert block._resolve_dotted(state, "shared_memory.topic") == "AI"


def test_resolve_dotted_metadata_still_works():
    """_resolve_dotted must still resolve 'metadata.*' paths."""
    block = _make_block()
    state = _make_state(metadata={"run_id": "xyz"})

    assert block._resolve_dotted(state, "metadata.run_id") == "xyz"


# ---------------------------------------------------------------------------
# _write_dotted — valid prefixes still work
# ---------------------------------------------------------------------------


def test_write_dotted_shared_memory_still_works():
    """_write_dotted must still write 'shared_memory.*' paths."""
    block = _make_block()
    state = _make_state(shared_memory={})

    new_state = block._write_dotted(state, "shared_memory.output", "done")
    assert new_state.shared_memory["output"] == "done"


def test_write_dotted_results_still_works():
    """_write_dotted must still write 'results.*' paths."""
    block = _make_block()
    state = _make_state(results={})
    br = BlockResult(output="written")

    new_state = block._write_dotted(state, "results.step_x", br)
    assert new_state.results["step_x"] == br
