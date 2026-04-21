"""Red tests for RUN-952 execution preparation and launch coordination.

These tests lock the coordinator split around preparation-time ownership:

- the requested snapshot/ref is the source of truth for launch preparation
- commit metadata lookup failures stay explicit instead of silently degrading
- cancellation that lands during prepare prevents execution from being scheduled

All tests in this file should fail on the pre-split implementation.
"""

import asyncio
import threading
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from runsight_api.logic.services.run_service import RunService

BRANCH_ONLY_YAML = """\
version: "1.0"
id: wf_branch_only
kind: workflow
workflow:
  name: Branch Only Workflow
  entry: analyze
  transitions:
    - from: analyze
      to: null
blocks:
  analyze:
    type: linear
    soul_ref: analyst
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
config: {}
"""

PREP_REGISTRY_YAML = """\
version: "1.0"
id: wf_prepare_parent
kind: workflow
workflow:
  name: Prepare Parent Workflow
  entry: child
  transitions:
    - from: child
      to: null
blocks:
  child:
    type: workflow
    workflow_ref: wf_prepare_child
config: {}
"""


def _db_engine():
    db_path = Path(tempfile.mkdtemp(prefix="run952-db-")) / "runsight.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str, workflow_id: str = "wf_1") -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=workflow_id,
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()


def _provider() -> Mock:
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


def _cancel_run(engine, run_id: str) -> None:
    session = Session(engine)
    try:
        run_service = RunService(RunRepository(session), workflow_repo=Mock())
        run_service.cancel_run(run_id)
    finally:
        session.close()


class TestRequestedSnapshotSourceOfTruth:
    @pytest.mark.asyncio
    async def test_launch_execution_keeps_parse_registry_and_commit_sha_bound_to_same_requested_snapshot(
        self,
    ):
        """A requested git snapshot must be sufficient to prepare a run.

        This single launch asserts that:
        - parse_workflow_yaml receives the requested snapshot YAML
        - runnable-registry construction receives that same snapshot context
        - the persisted commit metadata matches that same requested ref

        The working tree copy is not the source of truth once a branch/ref is
        explicitly requested.
        """

        engine = _db_engine()
        run_id = "run_952_snapshot_coherent"
        workflow_id = "wf_prepare_parent"
        requested_sha = "a" * 40
        _seed_run(engine, run_id, workflow_id=workflow_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = None
        workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/wf_prepare_parent.yaml")
        workflow_repo.build_runnable_workflow_registry.return_value = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = []
        git_service = Mock()
        git_service.read_file.return_value = PREP_REGISTRY_YAML
        git_service.get_sha.return_value = requested_sha

        service = ExecutionService(
            run_repo=Mock(),
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
                {"instruction": "use requested snapshot"},
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
    async def test_launch_execution_fails_explicitly_when_requested_snapshot_sha_is_missing(self):
        """Requested snapshot metadata must stay explicit.

        If the branch/ref SHA cannot be resolved, the run should fail during
        prepare instead of launching with a synthesized or missing commit.
        """

        engine = _db_engine()
        run_id = "run_952_missing_sha"
        _seed_run(engine, run_id)

        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(yaml="working-tree-yaml")
        workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/wf_1.yaml")
        provider_repo = Mock()
        provider_repo.list_all.return_value = [_provider()]
        git_service = Mock()
        git_service.read_file.return_value = BRANCH_ONLY_YAML
        git_service.get_sha.return_value = None

        service = ExecutionService(
            run_repo=Mock(),
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
                "wf_1",
                {"instruction": "require exact requested snapshot"},
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


class TestPrepareTimeCancellation:
    @pytest.mark.asyncio
    async def test_cancel_during_snapshot_read_prevents_execution_from_being_scheduled(self):
        """A cancel that lands during requested-snapshot loading must win."""

        engine = _db_engine()
        run_id = "run_952_cancel_read"
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
        workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/wf_1.yaml")
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
            run_repo=Mock(),
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
                "wf_1",
                {"instruction": "cancel during snapshot read"},
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
    async def test_cancel_during_registry_build_prevents_execution_from_being_scheduled(self):
        """Cancellation during downstream prepare work must not resurrect the run."""

        engine = _db_engine()
        run_id = "run_952_cancel_registry"
        _seed_run(engine, run_id, workflow_id="wf_prepare_parent")

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
        workflow_repo._get_path.return_value = Path("/tmp/custom/workflows/wf_prepare_parent.yaml")

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
            run_repo=Mock(),
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
                "wf_prepare_parent",
                {"instruction": "cancel during registry build"},
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
