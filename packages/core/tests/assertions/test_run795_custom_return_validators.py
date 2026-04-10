"""Red tests for RUN-795: custom assertion return validators."""

from __future__ import annotations

import importlib

import pytest
from runsight_core.assertions.base import GradingResult


def _load_symbols():
    module = importlib.import_module("runsight_core.assertions.custom")
    return (
        module._validate_bool_return,
        module._validate_grading_result_return,
        module._RETURN_VALIDATORS,
    )


class TestValidateBoolReturn:
    def test_true_maps_to_passing_grading_result(self):
        validate_bool_return, _, _ = _load_symbols()

        result = validate_bool_return(True, "budget_guard")

        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 1.0
        assert result.assertion_type == "custom:budget_guard"

    def test_false_maps_to_failing_grading_result(self):
        validate_bool_return, _, _ = _load_symbols()

        result = validate_bool_return(False, "budget_guard")

        assert isinstance(result, GradingResult)
        assert result.passed is False
        assert result.score == 0.0
        assert result.assertion_type == "custom:budget_guard"

    def test_non_bool_raises_type_error_with_plugin_name_and_actual_type(self):
        validate_bool_return, _, _ = _load_symbols()

        with pytest.raises(TypeError) as exc_info:
            validate_bool_return(0.85, "budget_guard")

        message = str(exc_info.value)
        assert "budget_guard" in message
        assert "returns: bool" in message
        assert "float" in message


class TestValidateGradingResultReturn:
    def test_pass_alias_is_accepted(self):
        _, validate_grading_result_return, _ = _load_symbols()

        result = validate_grading_result_return(
            {"pass": True, "score": 0.9},
            "budget_guard",
        )

        assert isinstance(result, GradingResult)
        assert result.passed is True
        assert result.score == 0.9
        assert result.reason == ""
        assert result.assertion_type == "custom:budget_guard"

    def test_passed_key_wins_over_aliases(self):
        _, validate_grading_result_return, _ = _load_symbols()

        result = validate_grading_result_return(
            {"passed": False, "pass_": True, "pass": True, "score": 0.2},
            "budget_guard",
        )

        assert result.passed is False
        assert result.score == 0.2

    def test_reason_is_coerced_to_string(self):
        _, validate_grading_result_return, _ = _load_symbols()

        result = validate_grading_result_return(
            {"passed": True, "score": 1, "reason": 404},
            "budget_guard",
        )

        assert result.passed is True
        assert result.score == 1.0
        assert result.reason == "404"

    def test_missing_score_key_raises_type_error_with_expected_and_actual_keys(self):
        _, validate_grading_result_return, _ = _load_symbols()

        with pytest.raises(TypeError) as exc_info:
            validate_grading_result_return({"passed": True}, "budget_guard")

        message = str(exc_info.value)
        assert "budget_guard" in message
        assert "score" in message
        assert "passed" in message

    def test_non_mapping_raises_type_error(self):
        _, validate_grading_result_return, _ = _load_symbols()

        with pytest.raises(TypeError) as exc_info:
            validate_grading_result_return(True, "budget_guard")

        message = str(exc_info.value)
        assert "budget_guard" in message
        assert "dict" in message
        assert "bool" in message

    def test_score_out_of_range_raises_value_error(self):
        _, validate_grading_result_return, _ = _load_symbols()

        with pytest.raises(ValueError) as exc_info:
            validate_grading_result_return({"passed": True, "score": 1.5}, "budget_guard")

        message = str(exc_info.value)
        assert "budget_guard" in message
        assert "between 0.0 and 1.0" in message


class TestReturnValidatorsTable:
    def test_dispatch_table_contains_supported_return_contracts(self):
        validate_bool_return, validate_grading_result_return, validators = _load_symbols()

        assert validators["bool"] is validate_bool_return
        assert validators["grading_result"] is validate_grading_result_return
        assert set(validators) == {"bool", "grading_result"}
