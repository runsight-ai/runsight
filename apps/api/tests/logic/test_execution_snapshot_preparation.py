"""Requested git snapshot preparation stays coherent and explicit."""

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from tests.logic.execution_preparation_helpers import (
    BRANCH_ONLY_YAML,
    PREP_REGISTRY_YAML,
    _db_engine,
    _prepared_inputs,
    _provider,
    _run_repo,
    _seed_run,
)


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
