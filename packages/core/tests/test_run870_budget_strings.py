"""
Failing tests for RUN-870: BudgetedContext — return strings instead of Task.

Tests cover:
- BudgetedContext has `instruction: str` and `context: str | None` fields
- BudgetedContext does NOT have a `task` field
- fit_to_budget() populates .instruction from budget-truncated instruction
- fit_to_budget() populates .context from budget-truncated context (or None)
- budget.py source does NOT import Task from runsight_core.primitives
- budget.py source does NOT contain any Task import
"""

import ast
from dataclasses import fields as dataclass_fields
from pathlib import Path
from unittest.mock import patch

import pytest
from runsight_core.memory.budget import (
    BudgetedContext,
    ContextBudgetRequest,
)

# ===========================================================================
# Helpers
# ===========================================================================

_BUDGET_PY = (
    Path(__file__).resolve().parent.parent / "src" / "runsight_core" / "memory" / "budget.py"
)


def _len_counter(text: str, model: str) -> int:
    """Mock TokenCounter: 1 token per character."""
    return len(text)


def _make_request(**overrides) -> ContextBudgetRequest:
    """Build a ContextBudgetRequest with sensible defaults, overrideable."""
    defaults = dict(
        model="test-model",
        system_prompt="You are a helpful assistant.",
        instruction="Summarize the document.",
        context="Some P2 context content.",
        conversation_history=[],
        budget_ratio=0.9,
        output_token_reserve=None,
    )
    defaults.update(overrides)
    return ContextBudgetRequest(**defaults)


# ===========================================================================
# 1. BudgetedContext shape — new fields
# ===========================================================================


class TestBudgetedContextHasStringFields:
    """BudgetedContext must have `instruction: str` and `context: str | None` fields."""

    def test_has_instruction_field(self):
        """BudgetedContext must expose an `instruction` field."""
        field_names = {f.name for f in dataclass_fields(BudgetedContext)}
        assert "instruction" in field_names, (
            "BudgetedContext is missing the `instruction` field (RUN-870)"
        )

    def test_has_context_field(self):
        """BudgetedContext must expose a `context` field."""
        field_names = {f.name for f in dataclass_fields(BudgetedContext)}
        assert "context" in field_names, "BudgetedContext is missing the `context` field (RUN-870)"

    def test_does_not_have_task_field(self):
        """BudgetedContext must NOT have a `task` field after RUN-870."""
        field_names = {f.name for f in dataclass_fields(BudgetedContext)}
        assert "task" not in field_names, (
            "BudgetedContext still has `task` field — should be replaced by "
            "`instruction` and `context` (RUN-870)"
        )

    def test_instruction_field_type_is_str(self):
        """BudgetedContext.instruction annotation must be str."""
        import typing

        hints = typing.get_type_hints(BudgetedContext)
        assert hints.get("instruction") is str, (
            f"BudgetedContext.instruction type hint should be str, got {hints.get('instruction')}"
        )

    def test_context_field_type_is_optional_str(self):
        """BudgetedContext.context annotation must be str | None (Optional[str])."""
        import typing

        hints = typing.get_type_hints(BudgetedContext)
        context_hint = hints.get("context")
        # Accept both `Optional[str]` and `str | None` — both resolve the same way
        origin = typing.get_origin(context_hint)
        args = typing.get_args(context_hint)
        assert origin is typing.Union and type(None) in args and str in args, (
            f"BudgetedContext.context type hint should be str | None, got {context_hint}"
        )


# ===========================================================================
# 2. fit_to_budget() populates .instruction
# ===========================================================================


class TestFitToBudgetInstructionField:
    """fit_to_budget() must set BudgetedContext.instruction from the request."""

    def test_instruction_set_from_request(self):
        """BudgetedContext.instruction equals the request instruction."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(instruction="Do something specific.")
        with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
            result = fit_to_budget(request, _len_counter)

        assert result.instruction == "Do something specific."

    def test_instruction_is_str(self):
        """BudgetedContext.instruction is a plain string, not an object."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(instruction="Plain string instruction.")
        with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
            result = fit_to_budget(request, _len_counter)

        assert isinstance(result.instruction, str)

    def test_instruction_not_accessible_via_task(self):
        """result.task should not exist — accessing it must raise AttributeError."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(instruction="Something.")
        with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
            result = fit_to_budget(request, _len_counter)

        with pytest.raises(AttributeError):
            _ = result.task  # noqa: B018


# ===========================================================================
# 3. fit_to_budget() populates .context
# ===========================================================================


class TestFitToBudgetContextField:
    """fit_to_budget() must set BudgetedContext.context from the budget-truncated context."""

    def test_context_set_from_request_when_within_budget(self):
        """BudgetedContext.context equals the original context when it fits."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(context="Important context here.")
        with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
            result = fit_to_budget(request, _len_counter)

        assert result.context == "Important context here."

    def test_context_is_str_or_none(self):
        """BudgetedContext.context is a str or None, not a Task object."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(context="Some context text.")
        with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
            result = fit_to_budget(request, _len_counter)

        assert isinstance(result.context, (str, type(None)))

    def test_context_truncated_when_over_budget(self):
        """BudgetedContext.context is shorter than original when P2 is trimmed."""
        from runsight_core.memory.budget import fit_to_budget

        # A long context with delimited entries so truncation has boundary to cut at
        long_context = "\n".join(f"=== Entry {i} ===\n{'word ' * 20}" for i in range(20))
        # Tight budget: system_prompt + instruction leave almost nothing for P2
        sys_prompt = "Sys."  # 4 chars
        instruction = "Go."  # 3 chars
        # Effective budget of 20 means only 13 tokens left for context
        request = _make_request(
            system_prompt=sys_prompt,
            instruction=instruction,
            context=long_context,
            conversation_history=[],
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=20):
            result = fit_to_budget(request, _len_counter)

        assert len(result.context) < len(long_context), (
            "context should be truncated when budget is tight"
        )

    def test_none_context_is_allowed(self):
        """BudgetedContext.context may be None when budget forces full drop."""
        from runsight_core.memory.budget import fit_to_budget

        # Extremely tight budget — only P1 fits, context must be dropped entirely
        request = _make_request(
            system_prompt="Hi",
            instruction="Go",
            context="=== Entry 1 ===\n" + "x" * 500,
            conversation_history=[],
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=10):
            # P1 = len("Hi") + len("Go") = 4 tokens; budget = 10; remaining = 6
            # Context is 500+ chars, so _truncate_context may return empty / None
            result = fit_to_budget(request, _len_counter)

        # Either empty string or None is acceptable for a fully-dropped context
        assert result.context is None or result.context == ""


# ===========================================================================
# 4. No Task import in budget.py
# ===========================================================================


class TestNoBudgetTaskImport:
    """budget.py must not import Task from runsight_core.primitives."""

    def test_no_task_import_from_primitives(self):
        """budget.py must not contain 'from runsight_core.primitives import Task'."""
        source = _BUDGET_PY.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module == "runsight_core.primitives":
                    imported_names = [alias.name for alias in node.names]
                    assert "Task" not in imported_names, (
                        "budget.py must not import Task from runsight_core.primitives (RUN-870)"
                    )

    def test_no_task_import_at_all(self):
        """budget.py must not import Task via any import statement."""
        source = _BUDGET_PY.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names = [alias.name for alias in node.names]
                assert "Task" not in imported_names, (
                    f"budget.py imports Task from '{node.module}' — must be removed (RUN-870)"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "Task", (
                        "budget.py has a bare `import Task` — must be removed (RUN-870)"
                    )

    def test_no_task_string_in_source(self):
        """budget.py source must not reference 'Task' as an identifier at module level."""
        source = _BUDGET_PY.read_text()
        # Check that the literal string 'Task(' does not appear (catches function calls)
        assert "Task(" not in source, (
            "budget.py still contains 'Task(' — Task instantiation must be removed (RUN-870)"
        )
