"""Shared fixtures for execution preparation behavior tests."""

import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

from runsight_core.redaction import RunRedactor
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_api.logic.services.run_service import RunService

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "execution_preparation"


def _load_workflow_fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


BRANCH_ONLY_YAML = _load_workflow_fixture("branch-only-workflow.yaml")
PREP_REGISTRY_YAML = _load_workflow_fixture("prepare-parent-workflow.yaml")


def _db_engine(tmp_path: Path):
    db_path = tmp_path / "runsight.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str, workflow_id: str = "branch-only-workflow") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=workflow_id,
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


def _provider() -> Mock:
    provider = Mock()
    provider.id = "fixture-provider"
    provider.type = "fixture-provider"
    provider.is_active = True
    provider.models = ["fixture-chat-model"]
    return provider


def _prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


def _cancel_run(engine, run_id: str) -> None:
    session = Session(engine)
    try:
        run_service = RunService(RunRepository(session), workflow_repo=Mock())
        run_service.cancel_run(run_id)
    finally:
        session.close()


def _run_repo(engine):
    return RunRepository(Session(engine))


def _write_repo_files(repo: Path, files: dict[str, str]) -> None:
    for relative_path, contents in files.items():
        target = repo / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dedent(contents).lstrip(), encoding="utf-8")


def _init_git_repo_with_files(tmp_path: Path, *, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    _write_repo_files(repo, files)

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
        ["git", "commit", "-m", "initial snapshot"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def _snapshot_missing_external_soul_workflow(workflow_id: str) -> str:
    return f"""\
version: "1.0"
id: {workflow_id}
kind: workflow
workflow:
  name: Snapshot Soul Workflow
  entry: review
  transitions:
    - from: review
      to: null
blocks:
  review:
    type: linear
    soul_ref: reviewer
souls: {{}}
config: {{}}
"""


def _working_tree_external_soul() -> str:
    return """\
id: reviewer
kind: soul
name: Reviewer
role: Reviewer
system_prompt: Review carefully.
provider: fixture-provider
model_name: fixture-chat-model
"""


def _snapshot_missing_tool_workflow(workflow_id: str) -> str:
    return f"""\
version: "1.0"
id: {workflow_id}
kind: workflow
tools:
  - helper_tool
workflow:
  name: Snapshot Tool Workflow
  entry: analyze
  transitions:
    - from: analyze
      to: null
blocks:
  analyze:
    type: linear
    soul_ref: assistant
souls:
  assistant:
    id: assistant
    kind: soul
    name: Assistant
    role: Assistant
    system_prompt: Help carefully.
    provider: fixture-provider
    model_name: fixture-chat-model
    tools:
      - helper_tool
config: {{}}
"""


def _working_tree_tool_definition() -> str:
    return """\
version: "1.0"
id: helper_tool
kind: tool
type: custom
executor: python
name: Helper Tool
description: Helper tool discovered only in the dirty working tree.
parameters:
  type: object
code: |
  def main(args):
      return {"ok": True}
"""


def _snapshot_missing_assertion_workflow(workflow_id: str, assertion_id: str) -> str:
    return f"""\
version: "1.0"
id: {workflow_id}
kind: workflow
workflow:
  name: Snapshot Assertion Workflow
  entry: analyze
  transitions:
    - from: analyze
      to: null
blocks:
  analyze:
    type: code
    code: |
      def main(data):
          return "calm response"
    assertions:
      - type: custom:{assertion_id}
config: {{}}
"""


def _working_tree_assertion_manifest(assertion_id: str) -> str:
    return f"""\
version: "1.0"
id: {assertion_id}
kind: assertion
name: Snapshot Guard
description: Assertion discovered only in the dirty working tree.
returns: bool
source: {assertion_id}.py
"""


def _working_tree_assertion_source() -> str:
    return """\
def get_assert(output, context):
    return output == "calm response"
"""
