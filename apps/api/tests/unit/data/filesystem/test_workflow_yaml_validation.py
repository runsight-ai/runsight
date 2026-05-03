"""Workflow YAML validation adapter behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from runsight_api.data.filesystem.workflow_yaml_validation import validate_yaml_content
from runsight_core.yaml.validation import ValidationResult

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "workflow_repo_tool_governance"


def _workflow_fixture_text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


class _EmptySoulScanner:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def scan(self):
        return SimpleNamespace(ids=lambda: {})


def _validate(
    tmp_path: Path,
    raw_yaml: str,
    *,
    declared_tool_result: ValidationResult,
    tool_governance_result: ValidationResult | None = None,
):
    return validate_yaml_content(
        base_path=tmp_path,
        workflow_id="governance-validation",
        raw_yaml=raw_yaml,
        registry_builder=lambda *args, **kwargs: None,
        declared_tool_definitions_validator=lambda *args, **kwargs: declared_tool_result,
        tool_governance_validator=lambda *args, **kwargs: (
            tool_governance_result or ValidationResult()
        ),
        has_workflow_blocks=lambda _file_def: False,
        soul_scanner_cls=_EmptySoulScanner,
    )


def test_validate_yaml_content_preserves_error_and_warning_payloads(tmp_path: Path) -> None:
    error_result = ValidationResult()
    error_result.add_warning(
        "Tool definition produced a warning alongside an error",
        source="tool_definitions",
        context="http",
    )
    error_result.add_error(
        "Tool definition validation exploded",
        source="tool_definitions",
        context="http",
    )

    valid, validation_error, warnings = _validate(
        tmp_path,
        _workflow_fixture_text("valid-declared-tool.yaml"),
        declared_tool_result=error_result,
    )

    assert valid is False
    assert validation_error is not None
    assert "Tool definition validation exploded" in validation_error
    assert warnings == error_result.warnings_as_dicts()


def test_validate_yaml_content_returns_warning_payloads_for_warning_only_result(
    tmp_path: Path,
) -> None:
    warning_result = ValidationResult()
    warning_result.add_warning(
        "Tool definition is only a warning",
        source="tool_definitions",
        context="lookup_profile",
    )

    valid, validation_error, warnings = _validate(
        tmp_path,
        _workflow_fixture_text("valid-declared-tool.yaml"),
        declared_tool_result=warning_result,
    )

    assert valid is True
    assert validation_error is None
    assert warnings == warning_result.warnings_as_dicts()


def test_validate_yaml_content_returns_empty_warning_list_for_schema_error(
    tmp_path: Path,
) -> None:
    valid, validation_error, warnings = _validate(
        tmp_path,
        _workflow_fixture_text("legacy-typed-tool.yaml"),
        declared_tool_result=ValidationResult(),
    )

    assert valid is False
    assert validation_error is not None
    assert warnings == []
