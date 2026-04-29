"""
RUN-838: failing tests for the core ValidationResult model.

These tests describe the canonical warning payload shape and the public
ValidationResult API expected to live in runsight_core.yaml.validation.
"""

from __future__ import annotations

from importlib import import_module


def _validation_module():
    return import_module("runsight_core.yaml.validation")


class TestValidationResultEmptyState:
    def test_empty_result_has_no_errors_warnings_or_summary(self):
        validation = _validation_module()

        result = validation.ValidationResult()

        assert result.has_errors is False
        assert result.has_warnings is False
        assert result.error_summary is None
        assert result.errors == []
        assert result.warnings == []


class TestValidationResultAdditions:
    def test_add_warning_sets_warning_state_without_errors(self):
        validation = _validation_module()

        result = validation.ValidationResult()
        result.add_warning(
            "missing custom tool",
            source="tool_governance",
            context="fetcher",
        )

        assert result.has_errors is False
        assert result.has_warnings is True
        assert len(result.warnings) == 1

        warning = result.warnings[0]
        assert warning.severity is validation.ValidationSeverity.warning
        assert warning.message == "missing custom tool"
        assert warning.source == "tool_governance"
        assert warning.context == "fetcher"

    def test_add_error_sets_error_state_and_summary(self):
        validation = _validation_module()

        result = validation.ValidationResult()
        result.add_error(
            "workflow file is malformed",
            source="parser",
            context="workflow.yml",
        )

        assert result.has_errors is True
        assert result.has_warnings is False
        assert len(result.errors) == 1
        assert result.error_summary is not None
        assert "workflow file is malformed" in result.error_summary

    def test_result_with_both_errors_and_warnings_exposes_both_lists(self):
        validation = _validation_module()

        result = validation.ValidationResult()
        result.add_warning("degraded tool resolution", source="tool_governance")
        result.add_error("fatal parser error", source="parser")

        assert result.has_errors is True
        assert result.has_warnings is True
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


class TestValidationResultMerge:
    def test_merge_mutates_self_and_combines_all_issues(self):
        validation = _validation_module()

        left = validation.ValidationResult()
        left.add_error("left-side error", source="parser")
        right = validation.ValidationResult()
        right.add_warning("right-side warning", source="tool_governance")

        left_issues_before = list(left.issues)
        right_issues_before = list(right.issues)

        left.merge(right)

        assert left.issues == left_issues_before + right_issues_before
        assert left.has_errors is True
        assert left.has_warnings is True
        assert right.issues == right_issues_before


class TestValidationResultSerialization:
    def test_warnings_as_dicts_serializes_warning_issues_only(self):
        validation = _validation_module()

        result = validation.ValidationResult()
        result.add_warning(
            "declared custom tool missing",
            source="tool_governance",
            context="fetcher",
        )
        result.add_error("fatal parser error", source="parser", context="workflow.yml")

        warnings = result.warnings_as_dicts()

        assert warnings == [
            {
                "message": "declared custom tool missing",
                "source": "tool_governance",
                "context": "fetcher",
            }
        ]

    def test_warnings_as_dicts_preserves_none_fields(self):
        validation = _validation_module()

        result = validation.ValidationResult()
        result.add_warning("warning without extra context")

        warnings = result.warnings_as_dicts()

        assert warnings == [
            {
                "message": "warning without extra context",
                "source": None,
                "context": None,
            }
        ]
