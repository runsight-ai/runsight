"""
Failing tests for RUN-259: fit_to_budget() Phase 1 — P1 accounting and safety valve.

Tests cover:
- fit_to_budget is importable and callable
- Returns BudgetedContext with correct task (instruction + context from request)
- Report has accurate p1_tokens (system_prompt + instruction tokens)
- P2 context and P3 history pass through unchanged
- ContextBudgetExceeded raised when P1 exceeds budget
- Safety valve: reduces output_reserve to 256 and retries before raising
- Report headroom = effective_budget - total_tokens
"""

from unittest.mock import patch

import pytest

from runsight_core.memory.budget import (
    BudgetedContext,
    ContextBudgetExceeded,
    ContextBudgetRequest,
)


# ===========================================================================
# Helpers
# ===========================================================================


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
        conversation_history=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
        budget_ratio=0.9,
        output_token_reserve=None,
    )
    defaults.update(overrides)
    return ContextBudgetRequest(**defaults)


# ===========================================================================
# 1. Importability and callability
# ===========================================================================


class TestFitToBudgetImportable:
    """fit_to_budget is importable from the budget module."""

    def test_fit_to_budget_importable(self):
        """fit_to_budget should be importable from runsight_core.memory.budget."""
        from runsight_core.memory.budget import fit_to_budget  # noqa: F401

    def test_fit_to_budget_is_callable(self):
        """fit_to_budget should be a callable function."""
        from runsight_core.memory.budget import fit_to_budget

        assert callable(fit_to_budget)


# ===========================================================================
# 2. Returns BudgetedContext with correct task
# ===========================================================================


class TestFitToBudgetReturnsCorrectTask:
    """fit_to_budget returns a BudgetedContext with task containing instruction and context."""

    def test_returns_budgeted_context(self):
        """Return type is BudgetedContext."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request()
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert isinstance(result, BudgetedContext)

    def test_task_has_instruction_from_request(self):
        """The task in BudgetedContext carries the original instruction."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(instruction="Do something specific.")
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.task.instruction == "Do something specific."

    def test_task_has_context_from_request(self):
        """The task in BudgetedContext carries the original context."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(context="Important context here.")
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.task.context == "Important context here."


# ===========================================================================
# 3. Report has accurate p1_tokens
# ===========================================================================


class TestFitToBudgetP1Accounting:
    """Report has accurate p1_tokens (system_prompt + instruction tokens)."""

    def test_p1_tokens_equals_system_prompt_plus_instruction(self):
        """p1_tokens = count(system_prompt) + count(instruction)."""
        from runsight_core.memory.budget import fit_to_budget

        sys_prompt = "System prompt text."
        instruction = "Instruction text."
        request = _make_request(system_prompt=sys_prompt, instruction=instruction)

        expected_p1 = len(sys_prompt) + len(instruction)

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p1_tokens == expected_p1

    def test_p1_tokens_with_empty_system_prompt(self):
        """p1_tokens handles empty system_prompt correctly (0 tokens for it)."""
        from runsight_core.memory.budget import fit_to_budget

        instruction = "Just an instruction."
        request = _make_request(system_prompt="", instruction=instruction)

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p1_tokens == len(instruction)

    def test_report_effective_budget_matches_get_model_budget(self):
        """Report's effective_budget equals what get_model_budget returns."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request()
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=50_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.report.effective_budget == 50_000


# ===========================================================================
# 4. P2 context and P3 history pass through unchanged
# ===========================================================================


class TestFitToBudgetPassthrough:
    """Phase 1: P2 context and P3 history pass through unchanged."""

    def test_p2_context_passes_through_unchanged(self):
        """The original context appears in the task without modification."""
        from runsight_core.memory.budget import fit_to_budget

        original_context = "=== Entry 1 ===\n=== Entry 2 ===\n=== Entry 3 ==="
        request = _make_request(context=original_context)

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.task.context == original_context

    def test_p3_history_passes_through_unchanged(self):
        """The conversation_history is passed through as messages without modification."""
        from runsight_core.memory.budget import fit_to_budget

        history = [
            {"role": "user", "content": "first message"},
            {"role": "assistant", "content": "first reply"},
            {"role": "user", "content": "second message"},
        ]
        request = _make_request(conversation_history=history)

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.messages == history

    def test_empty_context_passes_through(self):
        """Empty context string passes through as-is."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(context="")

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.task.context == ""

    def test_empty_history_passes_through(self):
        """Empty conversation history passes through as empty list."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(conversation_history=[])

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.messages == []


# ===========================================================================
# 5. ContextBudgetExceeded when P1 exceeds budget
# ===========================================================================


class TestFitToBudgetExceeded:
    """ContextBudgetExceeded raised when P1 alone exceeds budget."""

    def test_raises_when_p1_exceeds_budget(self):
        """When P1 tokens > effective_budget (even after safety valve), raise."""
        from runsight_core.memory.budget import fit_to_budget

        # Make P1 huge: system_prompt + instruction = 1000 chars = 1000 tokens
        # Budget is only 100 tokens, safety valve budget (output_reserve=256) still small
        request = _make_request(
            system_prompt="A" * 500,
            instruction="B" * 500,
        )

        # get_model_budget always returns a small budget no matter what
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100,
        ):
            with pytest.raises(ContextBudgetExceeded) as exc_info:
                fit_to_budget(request, _len_counter)

        assert exc_info.value.p1_tokens == 1000
        assert exc_info.value.model == "test-model"

    def test_exception_contains_effective_budget(self):
        """The raised exception carries the effective_budget value."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(
            system_prompt="A" * 300,
            instruction="B" * 300,
        )

        # Return small budget on both calls (original and safety valve retry)
        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=50,
        ):
            with pytest.raises(ContextBudgetExceeded) as exc_info:
                fit_to_budget(request, _len_counter)

        # The exception should report the safety-valve budget (the last attempt)
        assert exc_info.value.effective_budget is not None
        assert exc_info.value.p1_tokens == 600


# ===========================================================================
# 6. Safety valve — reduce output_reserve to 256 before giving up
# ===========================================================================


class TestFitToBudgetSafetyValve:
    """Safety valve: reduces output_reserve to 256 and retries before raising."""

    def test_safety_valve_retries_with_reduced_output_reserve(self):
        """When P1 exceeds initial budget, retry with output_reserve=256."""
        from runsight_core.memory.budget import fit_to_budget

        # system_prompt + instruction = 150 chars = 150 tokens with _len_counter
        request = _make_request(
            system_prompt="A" * 80,
            instruction="B" * 70,
            output_token_reserve=4096,
        )

        call_count = 0
        call_args_list = []

        def mock_get_model_budget(model, budget_ratio=0.9, output_reserve=None):
            nonlocal call_count
            call_count += 1
            call_args_list.append({"output_reserve": output_reserve})
            # First call with original output_reserve (4096) → small budget (100)
            # Second call with safety-valve output_reserve (256) → bigger budget (200)
            if call_count == 1:
                return 100  # P1 (150) exceeds this
            return 200  # P1 (150) fits this

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            side_effect=mock_get_model_budget,
        ):
            result = fit_to_budget(request, _len_counter)

        # Verify safety valve was triggered — two calls to get_model_budget
        assert call_count == 2
        # Second call should use output_reserve=256
        assert call_args_list[1]["output_reserve"] == 256
        # Should succeed since safety valve budget (200) > P1 (150)
        assert isinstance(result, BudgetedContext)

    def test_safety_valve_raises_if_still_exceeded(self):
        """If P1 still exceeds budget even after safety valve, raise."""
        from runsight_core.memory.budget import fit_to_budget

        # P1 = 500 tokens
        request = _make_request(
            system_prompt="A" * 250,
            instruction="B" * 250,
        )

        # Both attempts return budget < 500
        def mock_get_model_budget(model, budget_ratio=0.9, output_reserve=None):
            return 100  # Always too small

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            side_effect=mock_get_model_budget,
        ):
            with pytest.raises(ContextBudgetExceeded):
                fit_to_budget(request, _len_counter)

    def test_no_safety_valve_when_p1_fits_initially(self):
        """When P1 fits on first try, get_model_budget is called only once."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(
            system_prompt="short",
            instruction="text",
        )

        call_count = 0

        def mock_get_model_budget(model, budget_ratio=0.9, output_reserve=None):
            nonlocal call_count
            call_count += 1
            return 100_000  # P1 easily fits

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            side_effect=mock_get_model_budget,
        ):
            fit_to_budget(request, _len_counter)

        assert call_count == 1


# ===========================================================================
# 7. Report headroom = effective_budget - total_tokens
# ===========================================================================


class TestFitToBudgetReportHeadroom:
    """Report headroom = effective_budget - total_tokens."""

    def test_headroom_calculation(self):
        """headroom = effective_budget - total_tokens."""
        from runsight_core.memory.budget import fit_to_budget

        sys_prompt = "System."  # 7 chars
        instruction = "Do it."  # 6 chars
        context = "Context text."  # 13 chars
        history = [{"role": "user", "content": "msg"}]  # not counted for total yet (Phase 1)

        request = _make_request(
            system_prompt=sys_prompt,
            instruction=instruction,
            context=context,
            conversation_history=history,
        )

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        # headroom = effective_budget - total_tokens
        assert result.report.headroom == result.report.effective_budget - result.report.total_tokens

    def test_headroom_positive_when_under_budget(self):
        """When total tokens < effective_budget, headroom is positive."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(
            system_prompt="Hi",
            instruction="Go",
        )

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.report.headroom > 0

    def test_report_model_matches_request(self):
        """Report model field matches the request model."""
        from runsight_core.memory.budget import fit_to_budget

        request = _make_request(model="claude-3-opus")

        with patch(
            "runsight_core.memory.budget.get_model_budget",
            return_value=100_000,
        ):
            result = fit_to_budget(request, _len_counter)

        assert result.report.model == "claude-3-opus"
