from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from runsight_core.yaml.discovery import SoulScanner, ToolScanner, WorkflowScanner


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

    assert set(soul_index.ids()) == {"researcher"}
    assert set(tool_index.ids()) == {"helper"}
    assert set(workflow_index.ids()) == {"child-impl", "parent"}

    assert soul_index.get("custom/souls/researcher.yaml") is None
    assert tool_index.get("custom/tools/helper.yaml") is None
    assert workflow_index.get("child-impl") is not None
    assert workflow_index.get("child_flow") is None
    assert workflow_index.get("custom/workflows/child-impl.yaml") is None

    resolved = WorkflowScanner(tmp_path).resolve_ref("child-impl", index=workflow_index)
    assert resolved is not None
    assert resolved.path == paths["child"].resolve()


def test_all_scanners_support_git_snapshot_scan_with_real_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _write_shared_fixture(repo_path)
    git_service = _init_git_repo(repo_path, branch="sim/test")
    monkeypatch.chdir(repo_path)

    for scanner_cls in (SoulScanner, ToolScanner, WorkflowScanner):
        filesystem_index = scanner_cls(repo_path).scan()
        git_index = scanner_cls(repo_path).scan(git_ref="sim/test", git_service=git_service)

        assert filesystem_index.ids().keys() == git_index.ids().keys()

    workflow_git_index = WorkflowScanner(repo_path).scan(
        git_ref="sim/test", git_service=git_service
    )
    resolved = WorkflowScanner(repo_path).resolve_ref("child-impl", index=workflow_git_index)
    assert resolved is not None
    assert resolved.stem == "child-impl"
