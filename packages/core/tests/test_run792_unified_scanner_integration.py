from __future__ import annotations

import re
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import yaml
from runsight_core.yaml.discovery import SoulScanner, ToolScanner, WorkflowScanner
from runsight_core.yaml.parser import parse_workflow_yaml, validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile


class _GitReadService:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def read_file(self, path: str, ref: str) -> str:
        candidate = Path(path)
        if candidate.is_absolute():
            candidate = candidate.resolve().relative_to(self.repo_path.resolve())
        result = subprocess.run(
            ["git", "show", f"{ref}:{candidate.as_posix()}"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _tool_meta() -> dict:
    return {
        "version": "1.0",
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
    }


def _soul_meta() -> dict:
    return {
        "id": "researcher",
        "role": "Researcher",
        "system_prompt": "You research things.",
        "tools": ["helper"],
    }


def _code_workflow(name: str) -> dict:
    return {
        "version": "1.0",
        "config": {"model_name": "gpt-4o"},
        "interface": {"inputs": [], "outputs": []},
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
    _write_yaml(tool_path, _tool_meta())
    _write_yaml(child_path, _code_workflow("child_flow"))
    _write_yaml(parent_path, _parent_workflow("child_flow"))

    return {
        "soul": soul_path,
        "tool": tool_path,
        "child": child_path,
        "parent": parent_path,
    }


def _init_git_repo(repo_path: Path, *, branch: str) -> _GitReadService:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed unified scanner fixtures"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", branch], cwd=repo_path, check=True, capture_output=True
    )
    return _GitReadService(repo_path)


def test_unified_scanners_scan_shared_fixture_and_resolve_aliases(tmp_path: Path):
    paths = _write_shared_fixture(tmp_path)

    soul_index = SoulScanner(tmp_path).scan()
    tool_index = ToolScanner(tmp_path).scan()
    workflow_index = WorkflowScanner(tmp_path).scan()

    assert set(soul_index.stems()) == {"researcher"}
    assert set(tool_index.stems()) == {"helper"}
    assert set(workflow_index.stems()) == {"child-impl", "parent"}

    assert soul_index.get("custom/souls/researcher.yaml") is not None
    assert tool_index.get("custom/tools/helper.yaml") is not None
    assert workflow_index.get("child_flow") is not None
    assert workflow_index.get("custom/workflows/child-impl.yaml") is not None

    resolved = WorkflowScanner(tmp_path).resolve_ref("child_flow", index=workflow_index)
    assert resolved is not None
    assert resolved.path == paths["child"].resolve()


def test_all_scanners_support_git_snapshot_scan_with_real_repo(tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _write_shared_fixture(repo_path)
    git_service = _init_git_repo(repo_path, branch="sim/test")

    for scanner_cls in (SoulScanner, ToolScanner, WorkflowScanner):
        filesystem_index = scanner_cls(repo_path).scan()
        git_index = scanner_cls(repo_path).scan(git_ref="sim/test", git_service=git_service)

        assert filesystem_index.stems().keys() == git_index.stems().keys()

    workflow_git_index = WorkflowScanner(repo_path).scan(
        git_ref="sim/test", git_service=git_service
    )
    resolved = WorkflowScanner(repo_path).resolve_ref("child_flow", index=workflow_git_index)
    assert resolved is not None
    assert resolved.stem == "child-impl"


def test_workflow_repository_build_registry_matches_workflow_scanner_resolution(
    tmp_path: Path, workflow_repo_module
):
    paths = _write_shared_fixture(tmp_path)
    workflow_index = WorkflowScanner(tmp_path).scan()
    resolved = WorkflowScanner(tmp_path).resolve_ref("child_flow", index=workflow_index)

    assert resolved is not None
    assert resolved.path == paths["child"].resolve()

    with workflow_repo_module() as workflow_repo:
        repo = workflow_repo.WorkflowRepository(base_path=str(tmp_path))
        registry = repo.build_runnable_workflow_registry(
            "parent",
            paths["parent"].read_text(encoding="utf-8"),
        )

    child_by_name = registry.get("child_flow")
    child_by_path = registry.get("custom/workflows/child-impl.yaml")
    assert child_by_name.workflow.name == "child_flow"
    assert child_by_path.workflow.name == "child_flow"


def test_parser_and_validation_invoke_scanners_on_real_fixture(
    tmp_path: Path, workflow_repo_module
):
    paths = _write_shared_fixture(tmp_path)

    with workflow_repo_module() as workflow_repo:
        with (
            patch("runsight_core.yaml.parser.SoulScanner", wraps=SoulScanner) as soul_scanner_cls,
            patch("runsight_core.yaml.parser.ToolScanner", wraps=ToolScanner) as tool_scanner_cls,
        ):
            workflow_registry = workflow_repo.WorkflowRepository(
                base_path=str(tmp_path)
            ).build_runnable_workflow_registry(
                "parent",
                paths["parent"].read_text(encoding="utf-8"),
            )
            workflow = parse_workflow_yaml(
                str(paths["parent"]), workflow_registry=workflow_registry
            )

    assert workflow.name == "parent_flow"
    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in soul_scanner_cls.call_args_list
    )
    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in tool_scanner_cls.call_args_list
    )

    parent_file = RunsightWorkflowFile.model_validate(_parent_workflow("child_flow"))
    with patch(
        "runsight_core.yaml.parser.WorkflowScanner", wraps=WorkflowScanner
    ) as workflow_scanner_cls:
        validate_workflow_call_contracts(
            parent_file,
            base_dir=str(tmp_path),
            validation_index=None,
            current_workflow_ref=str(paths["parent"]),
            allow_filesystem_fallback=False,
        )

    assert any(
        call.args and Path(call.args[0]).resolve() == tmp_path.resolve()
        for call in workflow_scanner_cls.call_args_list
    )


def test_deleted_discovery_symbols_are_gone_from_production_code():
    legacy_symbols = (
        "discover_custom_assets",
        "discover_custom_tools",
        "_discover_souls",
        "_discover_blocks",
        "_discover_workflows",
        "_to_snake_case",
        "_discovery_module",
        "_build_workflow_validation_index",
        "_resolve_workflow_call_contract_ref",
        "_build_name_index",
        "_read_workflow_from_source",
        "_register_workflow_aliases",
        "_candidate_workflow_paths",
    )
    roots = [
        Path(__file__).resolve().parents[1] / "src",
        Path(__file__).resolve().parents[3] / "apps" / "api" / "src",
    ]

    patterns = {
        symbol: re.compile(rf"(?<!\w){re.escape(symbol)}(?!\w)") for symbol in legacy_symbols
    }
    matches: list[str] = []
    for root in roots:
        for py_file in root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for symbol, pattern in patterns.items():
                if pattern.search(content):
                    matches.append(f"{py_file}:{symbol}")

    assert matches == []
