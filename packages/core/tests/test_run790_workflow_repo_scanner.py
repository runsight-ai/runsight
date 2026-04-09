from __future__ import annotations

import importlib
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from runsight_core.yaml.discovery._base import ScanResult
from runsight_core.yaml.schema import RunsightWorkflowFile

_API_SRC = Path(__file__).resolve().parents[3] / "apps" / "api" / "src" / "runsight_api"
for module_name, module_path in {
    "runsight_api": _API_SRC,
    "runsight_api.core": _API_SRC / "core",
    "runsight_api.data": _API_SRC / "data",
    "runsight_api.data.filesystem": _API_SRC / "data" / "filesystem",
    "runsight_api.domain": _API_SRC / "domain",
}.items():
    if module_name not in sys.modules:
        module = ModuleType(module_name)
        module.__path__ = [str(module_path)]
        sys.modules[module_name] = module

if "structlog" not in sys.modules:
    structlog_stub = ModuleType("structlog")
    structlog_stub.contextvars = SimpleNamespace(
        bind_contextvars=lambda **_: None,
        unbind_contextvars=lambda *_, **__: None,
    )
    sys.modules["structlog"] = structlog_stub

if "ruamel" not in sys.modules:
    ruamel_stub = ModuleType("ruamel")
    ruamel_yaml_stub = ModuleType("ruamel.yaml")

    class _YAML:
        pass

    ruamel_yaml_stub.YAML = _YAML
    ruamel_stub.yaml = ruamel_yaml_stub
    sys.modules["ruamel"] = ruamel_stub
    sys.modules["ruamel.yaml"] = ruamel_yaml_stub

if "sqlmodel" not in sys.modules:
    sqlmodel_stub = ModuleType("sqlmodel")

    class _SQLModel:
        metadata = SimpleNamespace(
            create_all=lambda *_args, **_kwargs: None,
            drop_all=lambda *_args, **_kwargs: None,
        )

    sqlmodel_stub.SQLModel = _SQLModel
    sqlmodel_stub.create_engine = lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs)
    sys.modules["sqlmodel"] = sqlmodel_stub

WorkflowRepository = importlib.import_module(
    "runsight_api.data.filesystem.workflow_repo"
).WorkflowRepository


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


def test_workflow_repository_uses_workflow_scanner_for_registry_build(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
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

    with (
        patch("runsight_api.data.filesystem.workflow_repo.WorkflowScanner") as mock_scanner,
        patch("runsight_api.data.filesystem.workflow_repo.validate_workflow_call_contracts"),
    ):
        mock_scanner.return_value.scan.return_value = SimpleNamespace()
        mock_scanner.return_value.resolve_ref.return_value = child_result

        repo.build_runnable_workflow_registry("parent", raw_yaml)

    mock_scanner.assert_called_once_with(repo.base_path)
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.resolve_ref.assert_called_once()


def test_workflow_repository_legacy_scan_helpers_are_removed():
    assert not hasattr(WorkflowRepository, "_build_name_index")
    assert not hasattr(WorkflowRepository, "_read_workflow_from_source")
    assert not hasattr(WorkflowRepository, "_register_workflow_aliases")
    assert not hasattr(WorkflowRepository, "_candidate_workflow_paths")
