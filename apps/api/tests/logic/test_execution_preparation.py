"""Execution snapshot preparation ownership.

These tests lock the coordinator split around preparation-time ownership:

- the requested snapshot/ref is the source of truth for launch preparation
- commit metadata lookup failures stay explicit instead of silently degrading
- cancellation that lands during prepare prevents execution from being scheduled
- explicit snapshot parser-time discovery fails closed instead of mixing in
  dirty working-tree souls, tools, or assertions
"""

import asyncio
import logging
import subprocess
import threading
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.redaction import RunRedactor
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService, PreparedRunInputs
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


class TestRequestedSnapshotSourceOfTruth:
    @pytest.mark.asyncio
    async def test_launch_execution_keeps_parse_registry_and_commit_sha_bound_to_same_requested_snapshot(
        self,
        tmp_path: Path,
    ):
        """A requested git snapshot must be sufficient to prepare a run.

        This single launch asserts that:
        - parse_workflow_yaml receives the requested snapshot YAML
        - runnable-registry construction receives that same snapshot context
        - the persisted commit metadata matches that same requested ref

        The working tree copy is not the source of truth once a branch/ref is
        explicitly requested.
        """

        engine = _db_engine(tmp_path)
        run_id = "coherent-snapshot-run"
        workflow_id = "prepare-parent-workflow"
        requested_sha = "a" * 40
        _seed_run(engine, run_id, workflow_id=workflow_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/prepare-parent-workflow.yaml"
        )
        workflow_repo.build_runnable_workflow_registry.return_value = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = []
        git_service = Mock()
        git_service.read_file.return_value = PREP_REGISTRY_YAML
        git_service.get_sha.return_value = requested_sha

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ) as mock_parse,
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                workflow_id,
                _prepared_inputs({"instruction": "use requested snapshot"}),
                branch="feature/sim",
            )
            await asyncio.sleep(0)

        mock_parse.assert_called_once()
        assert mock_parse.call_args.args[0] == PREP_REGISTRY_YAML
        workflow_repo.build_runnable_workflow_registry.assert_called_once_with(
            workflow_id,
            PREP_REGISTRY_YAML,
            git_ref="feature/sim",
            git_service=git_service,
        )
        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.branch == "feature/sim"
            assert run.commit_sha == requested_sha
        assert run_workflow.await_count == 1, (
            "launch_execution should prepare from one coherent requested snapshot, "
            "persist its commit metadata, and schedule execution even when the "
            "working tree entity lookup is missing."
        )

    @pytest.mark.asyncio
    async def test_launch_execution_fails_explicitly_when_requested_snapshot_sha_is_missing(
        self,
        tmp_path: Path,
    ):
        """Requested snapshot metadata must stay explicit.

        If the branch/ref SHA cannot be resolved, the run should fail during
        prepare instead of launching with a synthesized or missing commit.
        """

        engine = _db_engine(tmp_path)
        run_id = "missing-sha-run"
        _seed_run(engine, run_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml="working-tree-yaml")
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/branch-only-workflow.yaml"
        )
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        git_service = Mock()
        git_service.read_file.return_value = BRANCH_ONLY_YAML
        git_service.get_sha.return_value = None

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ),
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                "branch-only-workflow",
                _prepared_inputs({"instruction": "require exact requested snapshot"}),
                branch="feature/sim",
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert "sha" in run.error.lower()

        assert run_workflow.await_count == 0, (
            "launch_execution must not schedule execution when the requested "
            "snapshot SHA cannot be resolved."
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("branch", ["feature/sim", "main"])
    async def test_launch_execution_fails_closed_when_git_snapshot_read_hits_old_fallback_error(
        self,
        tmp_path: Path,
        branch: str,
    ):
        """Fallback-eligible git snapshot read errors must still fail closed."""

        engine = _db_engine(tmp_path)
        run_id = "no-working-tree-fallback-run"
        _seed_run(engine, run_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml=BRANCH_ONLY_YAML)
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/branch-only-workflow.yaml"
        )
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        git_service = Mock()
        git_service.read_file.side_effect = subprocess.CalledProcessError(
            128,
            ["git", "show"],
            stderr="fatal: not a git repository",
        )

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ),
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                "branch-only-workflow",
                _prepared_inputs({"instruction": "require git snapshot"}),
                branch=branch,
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert branch in run.error
            assert "not a git repository" in run.error.lower()

        assert run_workflow.await_count == 0, (
            "launch_execution must fail instead of silently degrading to the working tree "
            "when the requested git snapshot cannot be read."
        )

    @pytest.mark.asyncio
    async def test_launch_execution_explicit_main_snapshot_requires_git_service(
        self,
        tmp_path: Path,
    ):
        engine = _db_engine(tmp_path)
        run_id = "main-snapshot-requires-git-run"
        _seed_run(engine, run_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml=BRANCH_ONLY_YAML)
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/branch-only-workflow.yaml"
        )
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ),
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                "branch-only-workflow",
                _prepared_inputs({"instruction": "require explicit main snapshot"}),
                branch="main",
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert "main" in run.error
            assert "git service unavailable" in run.error.lower()

        assert run_workflow.await_count == 0, (
            "An explicit branch='main' request must still be treated as a git snapshot request "
            "and fail closed when git_service is unavailable."
        )


class TestPrepareTimeCancellation:
    @pytest.mark.asyncio
    async def test_cancel_during_snapshot_read_prevents_execution_from_being_scheduled(
        self,
        tmp_path: Path,
    ):
        """A cancel that lands during requested-snapshot loading must win."""

        engine = _db_engine(tmp_path)
        run_id = "cancel-during-read-run"
        _seed_run(engine, run_id)

        read_started = threading.Event()
        allow_read_return = threading.Event()
        cancelled = threading.Event()

        def cancel_while_reading() -> None:
            assert read_started.wait(timeout=2), "snapshot read never started"
            _cancel_run(engine, run_id)
            cancelled.set()
            allow_read_return.set()

        canceller = threading.Thread(target=cancel_while_reading, daemon=True)
        canceller.start()

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml="working-tree-yaml")
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/branch-only-workflow.yaml"
        )
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        git_service = Mock()

        def blocked_read_file(*args, **kwargs):
            read_started.set()
            assert allow_read_return.wait(timeout=2), "cancel thread never released read_file"
            return BRANCH_ONLY_YAML

        git_service.read_file.side_effect = blocked_read_file
        git_service.get_sha.return_value = "b" * 40

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ),
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                "branch-only-workflow",
                _prepared_inputs({"instruction": "cancel during snapshot read"}),
                branch="feature/sim",
            )
            await asyncio.sleep(0)

        canceller.join(timeout=2)
        assert cancelled.is_set(), "cancel thread never updated the run"

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.cancelled

        assert run_workflow.await_count == 0, (
            "Cancellation during prepare must prevent launch_execution from "
            "scheduling background execution."
        )

    @pytest.mark.asyncio
    async def test_cancel_during_registry_build_prevents_execution_from_being_scheduled(
        self,
        tmp_path: Path,
    ):
        """Cancellation during downstream prepare work must not resurrect the run."""

        engine = _db_engine(tmp_path)
        run_id = "cancel-during-registry-run"
        _seed_run(engine, run_id, workflow_id="prepare-parent-workflow")

        registry_started = threading.Event()
        allow_registry_return = threading.Event()
        cancelled = threading.Event()

        def cancel_while_building_registry() -> None:
            assert registry_started.wait(timeout=2), "registry build never started"
            _cancel_run(engine, run_id)
            cancelled.set()
            allow_registry_return.set()

        canceller = threading.Thread(target=cancel_while_building_registry, daemon=True)
        canceller.start()

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml="working-tree-yaml")
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/prepare-parent-workflow.yaml"
        )

        def blocked_registry(*args, **kwargs):
            registry_started.set()
            assert allow_registry_return.wait(timeout=2), "cancel thread never released registry"
            return Mock()

        workflow_repo.build_runnable_workflow_registry.side_effect = blocked_registry

        provider_repo = Mock()
        provider_repo.list_all.return_value = []
        git_service = Mock()
        git_service.read_file.return_value = PREP_REGISTRY_YAML
        git_service.get_sha.return_value = "c" * 40

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=Mock(),
            ),
            patch.object(service, "_run_workflow", run_workflow),
        ):
            await service.launch_execution(
                run_id,
                "prepare-parent-workflow",
                _prepared_inputs({"instruction": "cancel during registry build"}),
                branch="feature/sim",
            )
            await asyncio.sleep(0)

        canceller.join(timeout=2)
        assert cancelled.is_set(), "cancel thread never updated the run"

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.cancelled

        assert run_workflow.await_count == 0, (
            "Cancellation during prepare must leave the run cancelled and "
            "prevent background execution from being scheduled."
        )

    @pytest.mark.asyncio
    async def test_cancelled_run_stays_cancelled_when_prepare_later_errors(
        self,
        tmp_path: Path,
    ):
        """Prepare-time errors after a winning cancel must not rewrite the run to failed."""

        engine = _db_engine(tmp_path)
        run_id = "cancel-before-prepare-error-run"
        _seed_run(engine, run_id)

        read_started = threading.Event()
        allow_read_error = threading.Event()
        cancelled = threading.Event()

        def cancel_before_prepare_error() -> None:
            assert read_started.wait(timeout=2), "snapshot read never started"
            _cancel_run(engine, run_id)
            cancelled.set()
            allow_read_error.set()

        canceller = threading.Thread(target=cancel_before_prepare_error, daemon=True)
        canceller.start()

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml="working-tree-yaml")
        workflow_repo._get_path.return_value = Path(
            "/tmp/custom/workflows/branch-only-workflow.yaml"
        )
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        git_service = Mock()

        def blocked_read_file(*args, **kwargs):
            read_started.set()
            assert allow_read_error.wait(timeout=2), "cancel thread never released read_file"
            raise ValueError("snapshot read exploded after cancellation")

        git_service.read_file.side_effect = blocked_read_file

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=git_service,
        )

        run_workflow = AsyncMock()
        with patch.object(service, "_run_workflow", run_workflow):
            await service.launch_execution(
                run_id,
                "branch-only-workflow",
                _prepared_inputs({"instruction": "cancel before prepare error"}),
                branch="feature/sim",
            )
            await asyncio.sleep(0)

        canceller.join(timeout=2)
        assert cancelled.is_set(), "cancel thread never updated the run"

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.cancelled

        assert run_workflow.await_count == 0, (
            "Cancellation that wins during prepare must remain terminal even if "
            "prepare later raises an error."
        )


@pytest.mark.asyncio
async def test_cancelled_run_is_not_resurrected_when_queued_execution_slot_opens(
    tmp_path: Path,
) -> None:
    engine = _db_engine(tmp_path)
    run_id = "cancelled-before-start-run"
    _seed_run(engine, run_id)

    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = Mock(yaml=BRANCH_ONLY_YAML)
    workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/branch-only-workflow.yaml")
    provider_repo = Mock()
    provider_repo.list_all.return_value = [_provider()]

    service = ExecutionService(
        run_repo=_run_repo(engine),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=engine,
        max_concurrent_runs=1,
    )

    await service._runtime.semaphore.acquire()

    mock_wf = Mock()
    mock_wf.run = AsyncMock()

    with patch(
        "runsight_api.logic.services.execution_service.parse_workflow_yaml",
        return_value=mock_wf,
    ):
        await service.launch_execution(
            run_id,
            "branch-only-workflow",
            _prepared_inputs({"instruction": "queued cancel should win"}),
        )
        await asyncio.sleep(0)

    queued_task = service._runtime.running_tasks[run_id]
    _cancel_run(engine, run_id)
    service._runtime.semaphore.release()
    await queued_task

    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        assert run.status == RunStatus.cancelled

    mock_wf.run.assert_not_awaited()


class TestSnapshotDiscoveryFailsClosed:
    @pytest.mark.asyncio
    async def test_launch_execution_fails_when_requested_snapshot_lacks_external_soul_but_working_tree_has_one(
        self,
        tmp_path: Path,
    ) -> None:
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
        from runsight_api.logic.services.git_service import GitService

        workflow_id = "snapshot-missing-soul-workflow"
        repo = _init_git_repo_with_files(
            tmp_path,
            files={
                f"custom/workflows/{workflow_id}.yaml": _snapshot_missing_external_soul_workflow(
                    workflow_id
                )
            },
        )
        _write_repo_files(repo, {"custom/souls/reviewer.yaml": _working_tree_external_soul()})

        engine = _db_engine(tmp_path)
        run_id = "missing-soul-snapshot-run"
        _seed_run(engine, run_id, workflow_id=workflow_id)

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=WorkflowRepository(base_path=str(repo)),
            provider_repo=Mock(list_all=Mock(return_value=[])),
            engine=engine,
            git_service=GitService(repo_path=repo),
        )

        run_workflow = AsyncMock()
        with patch.object(service, "_run_workflow", run_workflow):
            await service.launch_execution(
                run_id,
                workflow_id,
                _prepared_inputs({"instruction": "must fail closed"}),
                branch="main",
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert "main" in run.error
            assert "custom/souls/reviewer.yaml" in run.error
            assert "reviewer" in run.error.lower()

        assert run_workflow.await_count == 0, (
            "Explicit snapshot launches must fail instead of mixing committed "
            "workflow YAML with a dirty working-tree soul file."
        )

    @pytest.mark.asyncio
    async def test_launch_execution_fails_when_requested_snapshot_lacks_custom_tool_but_working_tree_has_one(
        self,
        tmp_path: Path,
    ) -> None:
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
        from runsight_api.logic.services.git_service import GitService

        workflow_id = "snapshot-missing-tool-workflow"
        repo = _init_git_repo_with_files(
            tmp_path,
            files={
                f"custom/workflows/{workflow_id}.yaml": _snapshot_missing_tool_workflow(workflow_id)
            },
        )
        _write_repo_files(repo, {"custom/tools/helper_tool.yaml": _working_tree_tool_definition()})

        engine = _db_engine(tmp_path)
        run_id = "missing-tool-snapshot-run"
        _seed_run(engine, run_id, workflow_id=workflow_id)

        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=WorkflowRepository(base_path=str(repo)),
            provider_repo=provider_repo,
            engine=engine,
            git_service=GitService(repo_path=repo),
        )

        run_workflow = AsyncMock()
        with patch.object(service, "_run_workflow", run_workflow):
            await service.launch_execution(
                run_id,
                workflow_id,
                _prepared_inputs({"instruction": "must fail closed"}),
                branch="main",
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert "helper_tool" in run.error.lower()

        assert run_workflow.await_count == 0, (
            "Explicit snapshot launches must fail instead of resolving custom "
            "tool metadata from the dirty working tree."
        )

    @pytest.mark.asyncio
    async def test_launch_execution_fails_when_requested_snapshot_lacks_custom_assertion_but_working_tree_has_one(
        self,
        tmp_path: Path,
    ) -> None:
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
        from runsight_api.logic.services.git_service import GitService

        workflow_id = "snapshot-missing-assertion-workflow"
        assertion_id = "snapshot_guard"
        repo = _init_git_repo_with_files(
            tmp_path,
            files={
                f"custom/workflows/{workflow_id}.yaml": _snapshot_missing_assertion_workflow(
                    workflow_id,
                    assertion_id,
                )
            },
        )
        _write_repo_files(
            repo,
            {
                f"custom/assertions/{assertion_id}.yaml": _working_tree_assertion_manifest(
                    assertion_id
                ),
                f"custom/assertions/{assertion_id}.py": _working_tree_assertion_source(),
            },
        )

        engine = _db_engine(tmp_path)
        run_id = "missing-assertion-snapshot-run"
        _seed_run(engine, run_id, workflow_id=workflow_id)

        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=WorkflowRepository(base_path=str(repo)),
            provider_repo=Mock(list_all=Mock(return_value=[])),
            engine=engine,
            git_service=GitService(repo_path=repo),
        )

        run_workflow = AsyncMock()
        with patch.object(service, "_run_workflow", run_workflow):
            await service.launch_execution(
                run_id,
                workflow_id,
                _prepared_inputs({"instruction": "must fail closed"}),
                branch="main",
            )
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.failed
            assert run.error is not None
            assert assertion_id in run.error

        assert run_workflow.await_count == 0, (
            "Explicit snapshot launches must fail instead of registering custom "
            "assertions from the dirty working tree."
        )

    @pytest.mark.asyncio
    async def test_launch_execution_logs_requested_ref_when_prepare_fails(
        self,
        tmp_path: Path,
        caplog,
    ) -> None:
        engine = _db_engine(tmp_path)
        run_id = "prepare-log-context-run"
        workflow_id = "prepare-log-context-workflow"
        requested_ref = "feature/snapshot-review"
        _seed_run(engine, run_id, workflow_id=workflow_id)

        workflow_repo = Mock()
        workflow_repo._get_path.return_value = Path(f"/tmp/custom/workflows/{workflow_id}.yaml")
        provider_repo = Mock()
        provider_repo.list_all.return_value = []
        service = ExecutionService(
            run_repo=_run_repo(engine),
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=engine,
            git_service=Mock(),
        )

        with (
            patch.object(
                service._preparation,
                "prepare_for_launch",
                side_effect=ValueError("Requested snapshot is missing custom/souls/reviewer.yaml"),
            ),
            caplog.at_level(
                logging.ERROR,
                logger="runsight_api.logic.services.execution_service",
            ),
        ):
            await service.launch_execution(
                run_id,
                workflow_id,
                _prepared_inputs({"instruction": "report requested ref"}),
                branch=requested_ref,
            )

        assert requested_ref in caplog.text
        assert "custom/souls/reviewer.yaml" in caplog.text
