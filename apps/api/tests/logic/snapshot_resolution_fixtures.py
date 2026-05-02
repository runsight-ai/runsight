from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_core.redaction import RunRedactor


def with_workflow_identity(workflow_id: str, yaml_text: str) -> str:
    return f"id: {workflow_id}\nkind: workflow\n" + dedent(yaml_text).strip() + "\n"


PARENT_WORKFLOW_YAML = """
version: "1.0"
inputs:
  instruction:
    type: string
    required: true
blocks:
  call_child:
    type: workflow
    workflow_ref: child
    inputs:
      topic: workflow.instruction
workflow:
  name: Parent Workflow
  entry: call_child
  transitions:
    - from: call_child
      to: null
config: {}
"""


CHILD_WORKFLOW_YAML = """
version: "1.0"
inputs:
  topic:
    type: string
    required: true
blocks:
  finish:
    type: code
    inputs:
      topic:
        from: workflow.topic
    code: |
      def main(data):
          return {"summary": data["topic"]}
workflow:
  name: Child Workflow
  entry: finish
  transitions:
    - from: finish
      to: null
"""


INVALID_CHILD_PUBLIC_INPUT_CONTRACT_YAML = """
version: "1.0"
inputs:
  UserId:
    type: string
    required: true
blocks:
  finish:
    type: code
    inputs:
      topic:
        from: workflow.topic
    code: |
      def main(data):
          return {"summary": data["topic"]}
workflow:
  name: Child Workflow
  entry: finish
  transitions:
    - from: finish
      to: null
"""


DIRTY_VALID_CHILD_WORKFLOW_YAML = """
version: "1.0"
inputs:
  topic:
    type: string
    required: true
blocks:
  finish:
    type: code
    inputs:
      topic:
        from: workflow.topic
    code: |
      def main(data):
          return {"summary": data["topic"]}
workflow:
  name: Dirty Child Workflow
  entry: finish
  transitions:
    - from: finish
      to: null
"""


MISSING_CHILD_REF_PARENT_WORKFLOW_YAML = """
version: "1.0"
inputs:
  instruction:
    type: string
    required: true
blocks:
  call_child:
    type: workflow
    workflow_ref: renamed-child
    inputs:
      topic: workflow.instruction
workflow:
  name: Parent Workflow
  entry: call_child
  transitions:
    - from: call_child
      to: null
config: {}
"""


RESERVED_CHILD_PUBLIC_INPUT_CONTRACT_YAML = """
version: "1.0"
inputs:
  workflow:
    type: string
    required: true
blocks:
  finish:
    type: code
    inputs:
      topic:
        from: workflow.topic
    code: |
      def main(data):
          return {"summary": data["topic"]}
workflow:
  name: Child Workflow
  entry: finish
  transitions:
    - from: finish
      to: null
"""


EMBEDDED_ID_PARENT_WORKFLOW_YAML = """
version: "1.0"
inputs:
  instruction:
    type: string
    required: true
blocks:
  call_child:
    type: workflow
    workflow_ref: child-impl
    inputs:
      topic: workflow.instruction
workflow:
  name: Parent Workflow
  entry: call_child
  transitions:
    - from: call_child
      to: null
config: {}
"""


EMBEDDED_ID_CHILD_WORKFLOW_YAML = """
version: "1.0"
inputs:
  topic:
    type: string
    required: true
blocks:
  finish:
    type: code
    inputs:
      topic:
        from: workflow.topic
    code: |
      def main(data):
          return {"summary": data["topic"]}
workflow:
  name: My Special Child
  entry: finish
  transitions:
    - from: finish
      to: null
"""


def resolvable_child_snapshot_files() -> dict[str, str]:
    return {
        "custom/workflows/parent.yaml": with_workflow_identity("parent", PARENT_WORKFLOW_YAML),
        "custom/workflows/child.yaml": with_workflow_identity("child", CHILD_WORKFLOW_YAML),
    }


def init_git_repo_with_invalid_child_contract_snapshot(tmp_path: Path) -> Path:
    repo = init_git_repo_with_nested_workflows(
        tmp_path,
        parent_yaml=PARENT_WORKFLOW_YAML,
        child_yaml=INVALID_CHILD_PUBLIC_INPUT_CONTRACT_YAML,
    )
    (repo / "custom" / "workflows" / "child.yaml").write_text(
        with_workflow_identity("child", DIRTY_VALID_CHILD_WORKFLOW_YAML),
        encoding="utf-8",
    )
    return repo


def init_git_repo_with_missing_child_ref(tmp_path: Path) -> tuple[Path, str]:
    parent_yaml = with_workflow_identity("parent", MISSING_CHILD_REF_PARENT_WORKFLOW_YAML)
    repo = init_git_repo_with_workflow_files(
        tmp_path,
        workflow_files={"parent.yaml": MISSING_CHILD_REF_PARENT_WORKFLOW_YAML},
    )
    return repo, parent_yaml


def init_git_repo_with_reserved_child_contract_snapshot(tmp_path: Path) -> Path:
    return init_git_repo_with_nested_workflows(
        tmp_path,
        parent_yaml=PARENT_WORKFLOW_YAML,
        child_yaml=RESERVED_CHILD_PUBLIC_INPUT_CONTRACT_YAML,
    )


def init_git_repo_with_embedded_id_child_on_feature_branch(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    workflows_dir = repo / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    (workflows_dir / "parent.yaml").write_text(
        with_workflow_identity("parent", EMBEDDED_ID_PARENT_WORKFLOW_YAML), encoding="utf-8"
    )
    (workflows_dir / "child-impl.yaml").write_text(
        with_workflow_identity("child-impl", EMBEDDED_ID_CHILD_WORKFLOW_YAML),
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "custom/workflows/parent.yaml"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "parent only on main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        ["git", "checkout", "-b", "feature-a"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add child-impl on feature-a"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    child_impl_path = workflows_dir / "child-impl.yaml"
    if child_impl_path.exists():
        child_impl_path.unlink()

    return repo


def init_git_repo_with_workflow_files(
    tmp_path: Path,
    *,
    workflow_files: dict[str, str],
) -> Path:
    repo = tmp_path / "repo"
    workflows_dir = repo / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    for filename, yaml_text in workflow_files.items():
        stem = Path(filename).stem
        (workflows_dir / filename).write_text(
            with_workflow_identity(stem, yaml_text), encoding="utf-8"
        )

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Runsight Tests"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial workflow snapshot"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def init_git_repo_with_nested_workflows(
    tmp_path: Path,
    *,
    parent_yaml: str,
    child_yaml: str,
) -> Path:
    return init_git_repo_with_workflow_files(
        tmp_path,
        workflow_files={"parent.yaml": parent_yaml, "child.yaml": child_yaml},
    )


def prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


def run_record():
    return SimpleNamespace(
        status="pending",
        error=None,
        branch=None,
        commit_sha=None,
        updated_at=None,
    )


def provider_repo_with_openai():
    provider_repo = Mock()
    provider_repo.list_all.return_value = [
        Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"], api_key=None)
    ]
    return provider_repo


def run_repo_with_pending_record():
    run_repo = Mock()
    run_repo.get_run.return_value = run_record()
    return run_repo


class SnapshotGitService:
    def __init__(self, *, snapshot_root: Path, snapshot_files: dict[str, str]) -> None:
        self.snapshot_root = snapshot_root
        self._snapshot_files = dict(snapshot_files)
        self.read_calls: list[tuple[str, str]] = []

    def list_files(self, ref: str, path_prefix: str) -> list[str]:
        del ref
        return sorted(
            path for path in self._snapshot_files if path.startswith(path_prefix.rstrip("/") + "/")
        )

    def read_file(self, path: str, ref: str) -> str:
        self.read_calls.append((path, ref))
        candidate = Path(path)
        if candidate.is_absolute():
            candidate = candidate.relative_to(self.snapshot_root)
        return self._snapshot_files[candidate.as_posix()]

    def get_sha(self, branch: str, path: str) -> str:
        return "8" * 40


def stub_runtime_execution(service) -> None:
    service._run_workflow = AsyncMock()
