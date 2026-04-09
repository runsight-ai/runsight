from __future__ import annotations

from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import patch

from runsight_core.yaml.discovery._base import ScanResult
from runsight_core.yaml.schema import RunsightWorkflowFile


def _workflow_file(name: str, *, child_ref: str | None = None) -> RunsightWorkflowFile:
    blocks = {}
    transitions = []
    entry = "finish"
    if child_ref is not None:
        entry = "call_child"
        blocks["call_child"] = {"type": "workflow", "workflow_ref": child_ref}
        transitions.append({"from": "call_child", "to": None})
    return RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "interface": {"inputs": [], "outputs": []},
            "blocks": blocks,
            "workflow": {"name": name, "entry": entry, "transitions": transitions},
        }
    )


def test_workflow_repository_uses_workflow_scanner_for_registry_build(
    tmp_path, workflow_repo_module
):
    child_path = (tmp_path / "custom" / "workflows" / "child.yaml").resolve()
    child_file = _workflow_file("child", child_ref=None)
    child_result = ScanResult(
        path=child_path,
        stem="child",
        relative_path="custom/workflows/child.yaml",
        item=child_file,
        aliases=frozenset(
            {str(child_path), "child", "custom/workflows/child.yaml", "child_workflow"}
        ),
    )
    raw_yaml = dedent(
        """\
        version: "1.0"
        interface:
          inputs: []
          outputs: []
        blocks:
          call_child:
            type: workflow
            workflow_ref: child
        workflow:
          name: parent
          entry: call_child
          transitions:
            - from: call_child
              to: null
        """
    )

    with workflow_repo_module() as workflow_repo:
        repo = workflow_repo.WorkflowRepository(base_path=str(tmp_path))
        with (
            patch.object(workflow_repo, "WorkflowScanner") as mock_scanner,
            patch.object(workflow_repo, "validate_workflow_call_contracts"),
        ):
            mock_scanner.return_value.scan.return_value = SimpleNamespace()
            mock_scanner.return_value.resolve_ref.return_value = child_result

            repo.build_runnable_workflow_registry("parent", raw_yaml)

    mock_scanner.assert_called_once_with(repo.base_path)
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.resolve_ref.assert_called_once()


def test_workflow_repository_legacy_scan_helpers_are_removed(workflow_repo_module):
    with workflow_repo_module() as workflow_repo:
        workflow_repository = workflow_repo.WorkflowRepository

    assert not hasattr(workflow_repository, "_build_name_index")
    assert not hasattr(workflow_repository, "_read_workflow_from_source")
    assert not hasattr(workflow_repository, "_register_workflow_aliases")
    assert not hasattr(workflow_repository, "_candidate_workflow_paths")
