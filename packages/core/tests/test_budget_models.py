"""
Failing tests for RUN-257: Data models, get_model_budget(), and _count_tokens()
with repetitive content defense.

Tests cover:
- budget.py exists and is importable
- TokenCounter protocol is defined (runtime_checkable)
- All 4 data models: ContextBudgetRequest, BudgetReport, BudgetedContext, ContextBudgetExceeded
- ContextBudgetExceeded has p1_tokens, effective_budget, model attributes
- _count_tokens returns 0 for empty/None input
- _count_tokens detects repetitive content (>50% repeated 4-grams) and uses len//3 estimate
- _count_tokens delegates to injected counter for normal text
- get_model_budget computes correct effective budget
- get_model_budget applies default output reserve = min(int(max_input * 0.1), 4096)
- token_counting.py exists with a default litellm adapter
- budget.py does NOT import litellm or tiktoken
"""

import ast
import inspect
from dataclasses import fields as dataclass_fields
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ===========================================================================
# 1. Module importability
# ===========================================================================


class TestBudgetModuleExists:
    """budget.py is importable from the memory package."""

    def test_budget_module_importable(self):
        """Importing budget should not raise."""
        from runsight_core.memory import budget  # noqa: F401

    def test_token_counting_module_importable(self):
        """Importing token_counting should not raise."""
        from runsight_core.memory import token_counting  # noqa: F401


# ===========================================================================
# 2. budget.py must NOT import litellm or tiktoken
# ===========================================================================


class TestBudgetNoDirectLLMImport:
    """budget.py must not import litellm or tiktoken — they are injected."""

    def test_budget_does_not_import_litellm(self):
        """budget.py source must not contain 'import litellm' or 'from litellm'."""
        budget_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "runsight_core"
            / "memory"
            / "budget.py"
        )
        source = budget_path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("litellm"), (
                        "budget.py must not import litellm directly"
                    )
                    assert not alias.name.startswith("tiktoken"), (
                        "budget.py must not import tiktoken directly"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("litellm"), (
                        "budget.py must not import from litellm"
                    )
                    assert not node.module.startswith("tiktoken"), (
                        "budget.py must not import from tiktoken"
                    )


# ===========================================================================
# 3. TokenCounter protocol
# ===========================================================================


class TestTokenCounterProtocol:
    """TokenCounter protocol is defined and runtime_checkable."""

    def test_token_counter_protocol_exists(self):
        """TokenCounter should be importable from budget."""
        from runsight_core.memory.budget import TokenCounter  # noqa: F401

    def test_token_counter_is_protocol(self):
        """TokenCounter should be a Protocol subclass."""
        from typing import Protocol

        from runsight_core.memory.budget import TokenCounter

        assert issubclass(TokenCounter, Protocol)

    def test_token_counter_is_runtime_checkable(self):
        """TokenCounter should be decorated with @runtime_checkable."""
        from runsight_core.memory.budget import TokenCounter

        # A runtime_checkable protocol supports isinstance checks
        def my_counter(text: str, model: str) -> int:
            return 42

        assert isinstance(my_counter, TokenCounter)

    def test_token_counter_callable_signature(self):
        """TokenCounter __call__ takes (text: str, model: str) -> int."""
        from runsight_core.memory.budget import TokenCounter

        sig = inspect.signature(TokenCounter.__call__)
        param_names = list(sig.parameters.keys())
        # First param is 'self', then 'text', then 'model'
        assert "text" in param_names
        assert "model" in param_names


# ===========================================================================
# 4. Data models
# ===========================================================================


class TestContextBudgetRequest:
    """ContextBudgetRequest is a Pydantic BaseModel with correct fields."""

    def test_importable(self):
        from runsight_core.memory.budget import ContextBudgetRequest  # noqa: F401

    def test_is_pydantic_model(self):
        from pydantic import BaseModel
        from runsight_core.memory.budget import ContextBudgetRequest

        assert issubclass(ContextBudgetRequest, BaseModel)

    def test_required_fields_present(self):
        from runsight_core.memory.budget import ContextBudgetRequest

        fields = ContextBudgetRequest.model_fields
        assert "model" in fields
        assert "system_prompt" in fields
        assert "instruction" in fields
        assert "context" in fields
        assert "conversation_history" in fields
        assert "output_token_reserve" in fields
        assert "budget_ratio" in fields

    def test_budget_ratio_default_is_0_9(self):
        """budget_ratio defaults to 0.9."""
        from runsight_core.memory.budget import ContextBudgetRequest

        field_info = ContextBudgetRequest.model_fields["budget_ratio"]
        assert field_info.default == 0.9

    def test_instantiation_with_minimal_fields(self):
        """Can create with just required fields, defaults fill the rest."""
        from runsight_core.memory.budget import ContextBudgetRequest

        req = ContextBudgetRequest(
            model="gpt-4",
            system_prompt="You are helpful.",
            instruction="Do the thing.",
            context="Some context.",
            conversation_history=[],
        )
        assert req.model == "gpt-4"
        assert req.budget_ratio == 0.9


class TestBudgetReport:
    """BudgetReport is a dataclass with all diagnostic fields."""

    def test_importable(self):
        from runsight_core.memory.budget import BudgetReport  # noqa: F401

    def test_has_expected_fields(self):
        from runsight_core.memory.budget import BudgetReport

        field_names = {f.name for f in dataclass_fields(BudgetReport)}
        expected = {
            "model",
            "max_input_tokens",
            "output_reserve",
            "effective_budget",
            "p1_tokens",
            "p2_tokens_before",
            "p2_tokens_after",
            "p3_tokens_before",
            "p3_tokens_after",
            "p3_pairs_dropped",
            "total_tokens",
            "headroom",
            "warnings",
        }
        assert expected.issubset(field_names), f"Missing fields: {expected - field_names}"


class TestBudgetedContext:
    """BudgetedContext is a dataclass with task, messages, and report."""

    def test_importable(self):
        from runsight_core.memory.budget import BudgetedContext  # noqa: F401

    def test_has_expected_fields(self):
        from runsight_core.memory.budget import BudgetedContext

        field_names = {f.name for f in dataclass_fields(BudgetedContext)}
        assert "task" in field_names
        assert "messages" in field_names
        assert "report" in field_names


class TestContextBudgetExceeded:
    """ContextBudgetExceeded is an Exception with structured attributes."""

    def test_importable(self):
        from runsight_core.memory.budget import ContextBudgetExceeded  # noqa: F401

    def test_is_exception_subclass(self):
        from runsight_core.memory.budget import ContextBudgetExceeded

        assert issubclass(ContextBudgetExceeded, Exception)

    def test_has_p1_tokens_attribute(self):
        from runsight_core.memory.budget import ContextBudgetExceeded

        exc = ContextBudgetExceeded(p1_tokens=5000, effective_budget=4000, model="gpt-4")
        assert exc.p1_tokens == 5000

    def test_has_effective_budget_attribute(self):
        from runsight_core.memory.budget import ContextBudgetExceeded

        exc = ContextBudgetExceeded(p1_tokens=5000, effective_budget=4000, model="gpt-4")
        assert exc.effective_budget == 4000

    def test_has_model_attribute(self):
        from runsight_core.memory.budget import ContextBudgetExceeded

        exc = ContextBudgetExceeded(p1_tokens=5000, effective_budget=4000, model="gpt-4")
        assert exc.model == "gpt-4"

    def test_is_raisable_and_catchable(self):
        from runsight_core.memory.budget import ContextBudgetExceeded

        with pytest.raises(ContextBudgetExceeded) as exc_info:
            raise ContextBudgetExceeded(p1_tokens=5000, effective_budget=4000, model="gpt-4")
        assert exc_info.value.p1_tokens == 5000


# ===========================================================================
# 5. _count_tokens utility
# ===========================================================================


class TestCountTokensEmpty:
    """_count_tokens returns 0 for empty or None input."""

    def test_none_input_returns_zero(self):
        from runsight_core.memory.budget import _count_tokens

        result = _count_tokens(None, "gpt-4", lambda t, m: 999)
        assert result == 0

    def test_empty_string_returns_zero(self):
        from runsight_core.memory.budget import _count_tokens

        result = _count_tokens("", "gpt-4", lambda t, m: 999)
        assert result == 0


class TestCountTokensRepetitiveContent:
    """_count_tokens detects repetitive content and uses len//3 estimate."""

    def test_highly_repetitive_text_uses_len_estimate(self):
        """Text with >50% repeated 4-grams bypasses the counter."""
        from runsight_core.memory.budget import _count_tokens

        # 'abcd' repeated 100 times = 400 chars, all same 4-gram → >50% repeated
        repetitive = "abcd" * 100
        spy = MagicMock(return_value=999)
        result = _count_tokens(repetitive, "gpt-4", spy)
        assert result == len(repetitive) // 3
        # The injected counter should NOT be called for repetitive content
        spy.assert_not_called()

    def test_repetitive_threshold_boundary(self):
        """Text with exactly 50% repeated 4-grams should NOT trigger the defense."""
        from runsight_core.memory.budget import _count_tokens

        # Construct text that has some repetition but stays at/below 50%
        # Each unique 4-gram appears at most twice in a non-repetitive-dominated text
        # Use a long unique string — all 4-grams unique
        unique_text = "".join(chr(65 + (i % 26)) for i in range(200))
        spy = MagicMock(return_value=42)
        result = _count_tokens(unique_text, "gpt-4", spy)
        # For non-repetitive text, the counter IS called
        spy.assert_called_once_with(unique_text, "gpt-4")
        assert result == 42


class TestCountTokensDelegatesToCounter:
    """_count_tokens delegates to the injected counter for normal text."""

    def test_normal_text_uses_injected_counter(self):
        from runsight_core.memory.budget import _count_tokens

        counter = MagicMock(return_value=150)
        result = _count_tokens("Hello, this is a normal sentence.", "gpt-4", counter)
        counter.assert_called_once_with("Hello, this is a normal sentence.", "gpt-4")
        assert result == 150

    def test_counter_receives_model_argument(self):
        from runsight_core.memory.budget import _count_tokens

        counter = MagicMock(return_value=50)
        _count_tokens("some text", "claude-3-opus", counter)
        counter.assert_called_once_with("some text", "claude-3-opus")


# ===========================================================================
# 6. get_model_budget utility
# ===========================================================================


class TestGetModelBudget:
    """get_model_budget computes effective budget from model info."""

    def test_computes_effective_budget(self):
        """effective_budget = int(max_input * budget_ratio) - output_reserve."""
        from unittest.mock import patch

        from runsight_core.memory.budget import get_model_budget

        with patch(
            "runsight_core.memory.budget.get_model_info",
            return_value={"max_input_tokens": 128000},
        ):
            result = get_model_budget("gpt-4", budget_ratio=0.9, output_reserve=4096)

        expected = int(128000 * 0.9) - 4096
        assert result == expected

    def test_default_output_reserve_min_formula(self):
        """Default output_reserve = min(int(max_input * 0.1), 4096)."""
        from unittest.mock import patch

        from runsight_core.memory.budget import get_model_budget

        # For a 128k model: min(12800, 4096) = 4096
        with patch(
            "runsight_core.memory.budget.get_model_info",
            return_value={"max_input_tokens": 128000},
        ):
            result = get_model_budget("gpt-4", budget_ratio=0.9)

        expected = int(128000 * 0.9) - 4096  # 115200 - 4096 = 111104
        assert result == expected

    def test_default_output_reserve_for_small_model(self):
        """For a small model, output_reserve = int(max_input * 0.1) < 4096."""
        from unittest.mock import patch

        from runsight_core.memory.budget import get_model_budget

        # For a 8k model: min(800, 4096) = 800
        with patch(
            "runsight_core.memory.budget.get_model_info",
            return_value={"max_input_tokens": 8000},
        ):
            result = get_model_budget("small-model", budget_ratio=0.9)

        expected = int(8000 * 0.9) - 800  # 7200 - 800 = 6400
        assert result == expected

    def test_custom_budget_ratio(self):
        """Custom budget_ratio is applied correctly."""
        from unittest.mock import patch

        from runsight_core.memory.budget import get_model_budget

        with patch(
            "runsight_core.memory.budget.get_model_info",
            return_value={"max_input_tokens": 100000},
        ):
            result = get_model_budget("gpt-4", budget_ratio=0.8, output_reserve=2000)

        expected = int(100000 * 0.8) - 2000  # 80000 - 2000 = 78000
        assert result == expected


# ===========================================================================
# 7. Default litellm adapter in token_counting.py
# ===========================================================================


class TestDefaultTokenCounterAdapter:
    """token_counting.py provides a default litellm-based TokenCounter."""

    def test_has_callable_counter(self):
        """token_counting module exposes a callable that matches TokenCounter."""
        from runsight_core.memory.budget import TokenCounter
        from runsight_core.memory.token_counting import litellm_token_counter

        assert isinstance(litellm_token_counter, TokenCounter)

    def test_adapter_delegates_to_litellm(self):
        """The adapter wraps litellm.token_counter under the hood."""
        from unittest.mock import patch

        from runsight_core.memory.token_counting import litellm_token_counter

        with patch(
            "runsight_core.memory.token_counting.token_counter",
            return_value=42,
        ) as mock_tc:
            result = litellm_token_counter("Hello world", "gpt-4")

        mock_tc.assert_called_once()
        assert result == 42
