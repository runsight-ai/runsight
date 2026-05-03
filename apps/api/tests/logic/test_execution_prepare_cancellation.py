"""Prepare-time cancellation remains terminal before execution is scheduled."""

import asyncio
import threading
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from tests.logic.execution_preparation_helpers import (
    BRANCH_ONLY_YAML,
    PREP_REGISTRY_YAML,
    _cancel_run,
    _db_engine,
    _prepared_inputs,
    _provider,
    _run_repo,
    _seed_run,
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
