"""Requested snapshot discovery fails closed without dirty working-tree fallback."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService
from tests.logic.execution_preparation_helpers import (
    _db_engine,
    _init_git_repo_with_files,
    _prepared_inputs,
    _provider,
    _run_repo,
    _seed_run,
    _snapshot_missing_assertion_workflow,
    _snapshot_missing_external_soul_workflow,
    _snapshot_missing_tool_workflow,
    _working_tree_assertion_manifest,
    _working_tree_assertion_source,
    _working_tree_external_soul,
    _working_tree_tool_definition,
    _write_repo_files,
)


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
