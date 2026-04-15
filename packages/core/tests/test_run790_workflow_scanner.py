from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from runsight_core.yaml.discovery._base import ScanResult
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile


def _workflow_data(
    workflow_id: str,
    *,
    workflow_name: str | None = None,
    child_ref: str | None = None,
) -> dict:
    blocks = {}
    transitions = []
    entry = "finish"
    if child_ref is not None:
        entry = "call_child"
        blocks["call_child"] = {"type": "workflow", "workflow_ref": child_ref}
        transitions.append({"from": "call_child", "to": None})
    workflow_name = workflow_name or workflow_id
    return {
        "version": "1.0",
        "id": workflow_id,
        "kind": "workflow",
        "interface": {"inputs": [], "outputs": []},
        "blocks": blocks,
        "workflow": {"name": workflow_name, "entry": entry, "transitions": transitions},
    }


def _write_workflow(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_workflow_scanner_is_public_and_originates_from_workflow_module():
    from runsight_core.yaml.discovery import WorkflowScanner

    workflow_module = importlib.import_module("runsight_core.yaml.discovery._workflow")

    assert WorkflowScanner.__module__ == workflow_module.WorkflowScanner.__module__


def test_workflow_scanner_uses_embedded_id_without_name_or_path_aliases(tmp_path: Path):
    from runsight_core.yaml.discovery import WorkflowScanner

    child_path = tmp_path / "custom" / "workflows" / "child.yaml"
    _write_workflow(child_path, _workflow_data("child", workflow_name="data_pipeline"))

    scanner = WorkflowScanner(str(tmp_path))
    scan_index = scanner.scan()

    assert scan_index.get("child") is not None
    assert scan_index.get("data_pipeline") is None
    assert scan_index.get("custom/workflows/child.yaml") is None

    assert scanner.resolve_ref("child", index=scan_index) is not None
    assert scanner.resolve_ref("custom/workflows/child.yaml", index=scan_index) is None


def test_workflow_scanner_rejects_embedded_id_filename_mismatch(tmp_path: Path):
    from runsight_core.yaml.discovery import WorkflowScanner

    child_path = tmp_path / "custom" / "workflows" / "legacy-stem.yaml"
    _write_workflow(child_path, _workflow_data("child", workflow_name="data_pipeline"))

    scanner = WorkflowScanner(str(tmp_path))

    with pytest.raises(ValueError, match="does not match filename stem"):
        scanner.scan()


def test_validate_workflow_call_contracts_uses_workflow_scanner_when_index_missing(tmp_path: Path):
    parent_file = RunsightWorkflowFile.model_validate(_workflow_data("parent", child_ref="child"))
    child_path = (tmp_path / "custom" / "workflows" / "child.yaml").resolve()
    child_file = RunsightWorkflowFile.model_validate(_workflow_data("child"))
    child_result = ScanResult(
        path=child_path,
        stem="child",
        relative_path="custom/workflows/child.yaml",
        item=child_file,
        aliases=frozenset({"child"}),
        entity_id="child",
    )

    with patch("runsight_core.yaml.parser.WorkflowScanner") as mock_scanner:
        mock_scan_index = Mock()
        mock_scan_index.get_all.return_value = [child_result]
        mock_scanner.return_value.scan.return_value = mock_scan_index

        validate_workflow_call_contracts(
            parent_file,
            base_dir=str(tmp_path),
            validation_index=None,
            current_workflow_ref=str(tmp_path / "custom" / "workflows" / "parent.yaml"),
        )

    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.resolve_ref.assert_not_called()


def test_parser_legacy_workflow_scan_helpers_are_removed():
    import runsight_core.yaml.parser as parser_module

    assert not hasattr(parser_module, "_build_workflow_validation_index")
    assert not hasattr(parser_module, "_resolve_workflow_call_contract_ref")
