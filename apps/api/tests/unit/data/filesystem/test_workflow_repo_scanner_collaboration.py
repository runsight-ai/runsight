from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
import runsight_api.data.filesystem.workflow_repo as workflow_repo_module
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_core.primitives import Soul
from runsight_core.yaml.discovery import SoulScanner, ToolScanner, WorkflowScanner
from runsight_core.yaml.discovery._base import ScanResult
from runsight_core.yaml.parser import parse_workflow_yaml, validate_workflow_call_contracts
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
            "id": name,
            "kind": "workflow",
            "blocks": blocks,
            "workflow": {"name": name, "entry": entry, "transitions": transitions},
        }
    )


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _soul_meta() -> dict:
    return {
        "id": "researcher",
        "kind": "soul",
        "name": "Researcher",
        "role": "Researcher",
        "system_prompt": "You research things.",
        "tools": ["helper"],
    }


def _code_workflow(name: str) -> dict:
    return {
        "version": "1.0",
        "id": "child-impl",
        "kind": "workflow",
        "config": {"model_name": "gpt-4o"},
        "blocks": {
            "finish": {
                "type": "code",
                "code": dedent(
                    """\
                    def main(data):
                        return {}
                    """
                ),
            }
        },
        "workflow": {
            "name": name,
            "entry": "finish",
            "transitions": [{"from": "finish", "to": None}],
        },
    }


def _parent_workflow(workflow_ref: str) -> dict:
    return {
        "version": "1.0",
        "id": "parent",
        "kind": "workflow",
        "config": {"model_name": "gpt-4o"},
        "tools": ["helper"],
        "blocks": {
            "research": {"type": "linear", "soul_ref": "researcher"},
            "call_child": {"type": "workflow", "workflow_ref": workflow_ref},
        },
        "workflow": {
            "name": "parent_flow",
            "entry": "research",
            "transitions": [
                {"from": "research", "to": "call_child"},
                {"from": "call_child", "to": None},
            ],
        },
    }


def _write_shared_fixture(base_dir: Path) -> dict[str, Path]:
    soul_path = base_dir / "custom" / "souls" / "researcher.yaml"
    tool_path = base_dir / "custom" / "tools" / "helper.yaml"
    child_path = base_dir / "custom" / "workflows" / "child-impl.yaml"
    parent_path = base_dir / "custom" / "workflows" / "parent.yaml"

    _write_yaml(soul_path, _soul_meta())
    _write_yaml(
        tool_path,
        {
            "version": "1.0",
            "id": "helper",
            "kind": "tool",
            "type": "custom",
            "executor": "python",
            "name": "Helper",
            "description": "Echo topic values.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            "code": "def main(args):\n    return {'topic': args.get('topic')}\n",
        },
    )
    _write_yaml(child_path, _code_workflow("child_flow"))
    _write_yaml(parent_path, _parent_workflow("child-impl"))

    return {
        "soul": soul_path,
        "tool": tool_path,
        "child": child_path,
        "parent": parent_path,
    }


def test_workflow_repository_uses_workflow_scanner_for_registry_build(tmp_path: Path):
    child_path = (tmp_path / "custom" / "workflows" / "child.yaml").resolve()
    child_file = _workflow_file("child", child_ref=None)
    child_result = ScanResult(
        path=child_path,
        stem="child",
        relative_path="custom/workflows/child.yaml",
        item=child_file,
        aliases=frozenset({"child"}),
        entity_id="child",
    )
    raw_yaml = dedent(
        """\
        version: "1.0"
        id: parent
        kind: workflow
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

    repo = WorkflowRepository(base_path=str(tmp_path))
    with (
        patch.object(workflow_repo_module, "WorkflowScanner") as mock_scanner,
        patch.object(workflow_repo_module, "validate_workflow_call_contracts"),
    ):
        mock_scanner.return_value.scan.return_value = SimpleNamespace(
            get_all=lambda: [child_result]
        )

        repo.build_runnable_workflow_registry("parent", raw_yaml)

    mock_scanner.assert_called_once_with(repo.base_path)
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.resolve_ref.assert_not_called()


def test_validate_yaml_content_uses_public_soul_scanner(tmp_path: Path):
    raw_yaml = dedent(
        """\
        id: scanner-migration
        kind: workflow
        version: "1.0"
        blocks:
          step:
            type: linear
            soul_ref: researcher
        workflow:
          name: scanner_migration
          entry: step
          transitions:
            - from: step
              to: null
        """
    )

    repo = WorkflowRepository(base_path=str(tmp_path))
    with patch.object(workflow_repo_module, "SoulScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.ids.return_value = {
            "researcher": Soul(
                id="researcher_1",
                kind="soul",
                name="Researcher",
                role="Researcher",
                system_prompt="Research",
            )
        }
        valid, error, warnings = repo._validate_yaml_content("scanner-migration", raw_yaml)

    assert valid is True
    assert error is None
    assert warnings == []
    mock_scanner.assert_called_once()
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.ids.assert_called_once()


def test_workflow_repository_build_registry_matches_workflow_scanner_resolution(tmp_path: Path):
    paths = _write_shared_fixture(tmp_path)
    workflow_index = WorkflowScanner(tmp_path).scan()
    resolved = WorkflowScanner(tmp_path).resolve_ref("child-impl", index=workflow_index)

    assert resolved is not None
    assert resolved.path == paths["child"].resolve()

    registry = WorkflowRepository(base_path=str(tmp_path)).build_runnable_workflow_registry(
        "parent",
        paths["parent"].read_text(encoding="utf-8"),
    )

    child_by_id = registry.get("child-impl")
    assert child_by_id.workflow.name == "child_flow"
    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get("child_flow")
    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get("custom/workflows/child-impl.yaml")


def test_parser_and_validation_invoke_scanners_on_real_fixture(tmp_path: Path):
    paths = _write_shared_fixture(tmp_path)

    with (
        patch("runsight_core.yaml.parser.SoulScanner", wraps=SoulScanner) as soul_scanner_cls,
        patch("runsight_core.yaml.parser.ToolScanner", wraps=ToolScanner) as tool_scanner_cls,
    ):
        workflow_registry = WorkflowRepository(
            base_path=str(tmp_path)
        ).build_runnable_workflow_registry(
            "parent",
            paths["parent"].read_text(encoding="utf-8"),
        )
        workflow = parse_workflow_yaml(str(paths["parent"]), workflow_registry=workflow_registry)

    assert workflow.name == "parent_flow"
    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in soul_scanner_cls.call_args_list
    )
    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in tool_scanner_cls.call_args_list
    )

    parent_file = RunsightWorkflowFile.model_validate(_parent_workflow("child-impl"))
    with patch(
        "runsight_core.yaml.parser.WorkflowScanner", wraps=WorkflowScanner
    ) as workflow_scanner_cls:
        validate_workflow_call_contracts(
            parent_file,
            base_dir=str(tmp_path),
            validation_index=None,
            current_workflow_ref=str(paths["parent"]),
        )

    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in workflow_scanner_cls.call_args_list
    )
