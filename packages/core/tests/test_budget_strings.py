"""Smoke coverage for BudgetedContext string fields used by budget fitting."""

from dataclasses import fields as dataclass_fields
from unittest.mock import patch

import pytest
from runsight_core.memory.budget import BudgetedContext, ContextBudgetRequest, fit_to_budget


def _len_counter(text: str, model: str) -> int:
    return len(text)


def _make_request(**overrides) -> ContextBudgetRequest:
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


def test_budgeted_context_exposes_instruction_and_context_without_task():
    import typing

    field_names = {field.name for field in dataclass_fields(BudgetedContext)}
    hints = typing.get_type_hints(BudgetedContext)

    assert {"instruction", "context"} <= field_names
    assert "task" not in field_names
    assert hints["instruction"] is str
    assert str in typing.get_args(hints["context"])
    assert type(None) in typing.get_args(hints["context"])


def test_fit_to_budget_returns_budgeted_strings_not_task_object():
    request = _make_request(
        instruction="Do something specific.",
        context="Important context here.",
    )

    with patch("runsight_core.memory.budget.get_model_budget", return_value=100_000):
        result = fit_to_budget(request, _len_counter)

    assert result.instruction == "Do something specific."
    assert result.context == "Important context here."
    assert isinstance(result.instruction, str)
    assert isinstance(result.context, str)
    with pytest.raises(AttributeError):
        _ = result.task
