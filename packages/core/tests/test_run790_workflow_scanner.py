from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from runsight_core.yaml.discovery._base import ScanResult
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile


def _workflow_data(name: str, *, child_ref: str | None = None) -> dict:
    blocks = {}
    transitions = []
    entry = "finish"
    if child_ref is not None:
        entry = "call_child"
        blocks["call_child"] = {"type": "workflow", "workflow_ref": child_ref}
        transitions.append({"from": "call_child", "to": None})
    return {
        "version": "1.0",
        "interface": {"inputs": [], "outputs": []},
        "blocks": blocks,
        "workflow": {"name": name, "entry": entry, "transitions": transitions},
    }


def _write_workflow(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_workflow_scanner_is_public_and_originates_from_workflow_module():
    from runsight_core.yaml.discovery import WorkflowScanner

    workflow_module = importlib.import_module("runsight_core.yaml.discovery._workflow")

    assert WorkflowScanner.__module__ == workflow_module.WorkflowScanner.__module__


def test_workflow_scanner_supports_name_alias_and_path_resolution(tmp_path: Path):
    from runsight_core.yaml.discovery import WorkflowScanner

    child_path = tmp_path / "custom" / "workflows" / "child.yaml"
    _write_workflow(child_path, _workflow_data("data_pipeline"))

    scanner = WorkflowScanner(str(tmp_path))
    scan_index = scanner.scan()

    assert scan_index.get("child") is not None
    assert scan_index.get("data_pipeline") is not None
    assert scan_index.get("custom/workflows/child.yaml") is not None

    assert scanner.resolve_ref("child", index=scan_index) is not None
    assert scanner.resolve_ref("custom/workflows/child.yaml") is not None


def test_validate_workflow_call_contracts_uses_workflow_scanner_when_index_missing(tmp_path: Path):
    parent_file = RunsightWorkflowFile.model_validate(_workflow_data("parent", child_ref="child"))
    child_path = (tmp_path / "custom" / "workflows" / "child.yaml").resolve()
    child_file = RunsightWorkflowFile.model_validate(_workflow_data("child"))
    child_result = ScanResult(
        path=child_path,
        stem="child",
        relative_path="custom/workflows/child.yaml",
        item=child_file,
        aliases=frozenset(
            {
                str(child_path),
                "child",
                "custom/workflows/child.yaml",
                "child_workflow",
            }
        ),
    )

    with patch("runsight_core.yaml.parser.WorkflowScanner") as mock_scanner:
        mock_scan_index = Mock()
        mock_scan_index.get_all.return_value = []
        mock_scanner.return_value.scan.return_value = mock_scan_index
        mock_scanner.return_value.resolve_ref.return_value = child_result

        validate_workflow_call_contracts(
            parent_file,
            base_dir=str(tmp_path),
            validation_index=None,
            current_workflow_ref=str(tmp_path / "custom" / "workflows" / "parent.yaml"),
            allow_filesystem_fallback=False,
        )

    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.resolve_ref.assert_called_once()


def test_parser_legacy_workflow_scan_helpers_are_removed():
    import runsight_core.yaml.parser as parser_module

    assert not hasattr(parser_module, "_build_workflow_validation_index")
    assert not hasattr(parser_module, "_resolve_workflow_call_contract_ref")
