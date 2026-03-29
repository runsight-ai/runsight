"""
RED tests for RUN-182: Rename state.messages -> state.execution_log.

Pure mechanical rename — no behavioral change. The field `messages` on
WorkflowState becomes `execution_log`.

Every test MUST FAIL against the current codebase (field is still `messages`)
and PASS once the Green agent implements the rename.
"""

import pathlib


from runsight_core.state import WorkflowState


# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
IMPLEMENTATIONS_PY = (
    REPO_ROOT / "libs" / "core" / "src" / "runsight_core" / "blocks" / "implementations.py"
)


# ─── Field existence tests ───────────────────────────────────────────────────


class TestFieldExistence:
    """WorkflowState must expose `execution_log` and NOT `messages`."""

    def test_has_execution_log_field(self):
        """execution_log should exist as a field on WorkflowState."""
        assert "execution_log" in WorkflowState.model_fields

    def test_messages_field_removed(self):
        """messages should no longer exist as a field on WorkflowState."""
        assert "messages" not in WorkflowState.model_fields

    def test_execution_log_in_model_fields_keys(self):
        """execution_log must appear in the Pydantic model_fields dict."""
        field_names = list(WorkflowState.model_fields.keys())
        assert "execution_log" in field_names


# ─── Behavioral tests ────────────────────────────────────────────────────────


class TestBehavior:
    """The renamed field must behave identically to the old `messages` field."""

    def test_default_is_empty_list(self):
        """execution_log should default to an empty list."""
        state = WorkflowState()
        assert state.execution_log == []

    def test_construct_with_execution_log(self):
        """Constructing WorkflowState with execution_log kwarg should work."""
        entries = [{"role": "system", "content": "test"}]
        state = WorkflowState(execution_log=entries)
        assert state.execution_log == entries

    def test_access_execution_log(self):
        """state.execution_log must return the list."""
        entries = [
            {"role": "system", "content": "init"},
            {"role": "assistant", "content": "done"},
        ]
        state = WorkflowState(execution_log=entries)
        assert len(state.execution_log) == 2
        assert state.execution_log[0]["role"] == "system"

    def test_model_copy_with_execution_log(self):
        """model_copy(update={'execution_log': ...}) must work."""
        state = WorkflowState()
        new_entry = {"role": "system", "content": "appended"}
        updated = state.model_copy(update={"execution_log": state.execution_log + [new_entry]})
        assert len(updated.execution_log) == 1
        assert updated.execution_log[0]["content"] == "appended"
