"""Red tests for RUN-127 and RUN-423: ExecutionService background execution.

These tests target the new ExecutionService that wires POST /runs to workflow.run()
with background asyncio execution. All tests should FAIL until the implementation exists.
"""

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

# --- Import target (does not exist yet — tests must fail on import) ---


def _import_execution_service():
    """Deferred import so individual tests can report failure clearly."""
    from runsight_api.logic.services.execution_service import ExecutionService

    return ExecutionService


def _init_git_repo_with_workflow(
    tmp_path: Path,
    *,
    workflow_id: str,
    main_yaml: str,
) -> Path:
    repo = tmp_path / "repo"
    workflow_path = repo / "custom" / "workflows" / f"{workflow_id}.yaml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(main_yaml)

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
        ["git", "commit", "-m", "initial workflow"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


VALID_RUNTIME_YAML = """
version: "1.0"
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: test
souls:
  test:
    id: soul_1
    role: tester
    system_prompt: hello
    provider: openai
    model_name: gpt-4o
config: {}
"""


# ---------------------------------------------------------------------------
# 1. ExecutionService instantiation
# ---------------------------------------------------------------------------


class TestExecutionServiceInit:
    def test_execution_service_exists(self):
        """ExecutionService class can be imported from logic.services.execution_service."""
        ExecutionService = _import_execution_service()
        assert ExecutionService is not None

    def test_accepts_required_dependencies(self):
        """ExecutionService.__init__ accepts run_repo, workflow_repo, provider_repo."""
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )
        assert svc.run_repo is run_repo
        assert svc.workflow_repo is workflow_repo
        assert svc.provider_repo is provider_repo


# ---------------------------------------------------------------------------
# 2. launch_execution — happy path
# ---------------------------------------------------------------------------


class TestLaunchExecution:
    @pytest.fixture
    def deps(self):
        return Mock(), Mock(), Mock()  # run_repo, workflow_repo, provider_repo

    @pytest.mark.asyncio
    async def test_launch_execution_registers_task(self):
        """launch_execution adds run_id to _running_tasks."""
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        # Provide a valid YAML string that workflow_repo returns
        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        # Provider returns an API key
        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_1", "wf_1", {"instruction": "do stuff"})

            # Task should be tracked
            assert "run_1" in svc._running_tasks

    @pytest.mark.asyncio
    async def test_launch_execution_returns_immediately(self):
        """launch_execution returns before the workflow finishes (background task)."""
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        execution_started = asyncio.Event()
        execution_finish = asyncio.Event()

        async def slow_run(*args, **kwargs):
            execution_started.set()
            await execution_finish.wait()
            from runsight_core.state import WorkflowState

            return WorkflowState()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = Mock()
            mock_wf.run = slow_run
            mock_parse.return_value = mock_wf

            # launch_execution should return before slow_run completes
            await svc.launch_execution("run_2", "wf_1", {"instruction": "test"})

            # The method returned but workflow hasn't completed
            assert "run_2" in svc._running_tasks

            # Let the background task finish
            execution_finish.set()
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_launch_execution_reads_yaml_from_requested_branch(self, tmp_path: Path):
        """RUN-423: requested simulation branches must supply their own YAML content."""
        ExecutionService = _import_execution_service()
        from runsight_api.logic.services.git_service import GitService
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        main_yaml = """
version: "1.0"
workflow:
  name: Main Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: main-soul
souls:
  main-soul:
    id: soul_main
    role: tester
    system_prompt: hello
    provider: openai
    model_name: gpt-4o
config: {}
"""
        sim_yaml = """
version: "1.0"
workflow:
  name: Simulation Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: sim-soul
souls:
  sim-soul:
    id: soul_sim
    role: tester
    system_prompt: hello
    provider: openai
    model_name: gpt-4o
config: {}
"""
        repo = _init_git_repo_with_workflow(tmp_path, workflow_id="wf_1", main_yaml=main_yaml)
        git_service = GitService(repo_path=repo)
        sim_branch = git_service.create_sim_branch(
            workflow_slug="wf_1",
            yaml_content=sim_yaml,
            yaml_path="custom/workflows/wf_1.yaml",
        ).branch

        run_repo = Mock()
        provider_repo = Mock()
        provider_repo.list_all.return_value = []
        workflow_repo = WorkflowRepository(base_path=str(repo))
        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            git_service=git_service,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            mock_wf = Mock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "run_branch_yaml",
                "wf_1",
                {"instruction": "execute simulation"},
                branch=sim_branch,
            )

            mock_parse.assert_called_once()
            workflow_def = mock_parse.call_args.args[0]
            assert workflow_def["workflow"]["name"] == "Simulation Workflow"
            assert workflow_def["workflow"]["name"] != "Main Workflow"


# ---------------------------------------------------------------------------
# 3. launch_execution — auto-cleanup via done callback
# ---------------------------------------------------------------------------


class TestAutoCleanup:
    @pytest.mark.asyncio
    async def test_task_removed_after_completion(self):
        """After background task completes, run_id is removed from _running_tasks."""
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        run_repo.update_run = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            from runsight_core.state import WorkflowState

            mock_wf = Mock()
            mock_wf.run = AsyncMock(return_value=WorkflowState())
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_cleanup", "wf_1", {"instruction": "test"})

            # Wait for background task to finish and cleanup callback to fire
            await asyncio.sleep(0.1)

            assert "run_cleanup" not in svc._running_tasks


# ---------------------------------------------------------------------------
# 4. launch_execution — error paths
# ---------------------------------------------------------------------------


class TestLaunchExecutionErrors:
    @pytest.mark.asyncio
    async def test_invalid_yaml_sets_run_failed(self):
        """If workflow YAML is invalid/unparseable, Run status is set to failed."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_err1",
            workflow_id="wf_bad",
            workflow_name="wf_bad",
            status=RunStatus.pending,
            task_json="{}",
        )
        run_repo = Mock()
        run_repo.get_run.return_value = run
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = "this: is: not: valid: workflow"
        workflow_repo.get_by_id.return_value = mock_entity

        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        await svc.launch_execution("run_err1", "wf_bad", {"instruction": "test"})

        # Wait for background task to fail
        await asyncio.sleep(0.1)

        # Run should have been updated to failed
        run_repo.update_run.assert_called()
        updated_run = run_repo.update_run.call_args[0][0]
        assert updated_run.status == RunStatus.failed
        assert updated_run.error is not None

    @pytest.mark.asyncio
    async def test_no_provider_no_env_var_sets_run_failed(self):
        """If provider table is empty and no env var, Run status = failed (via observer)."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        # Use real in-memory DB so ExecutionObserver can write status
        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_nokey"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        # Valid workflow YAML that needs an LLM call (non-placeholder block)
        mock_entity = Mock()
        mock_entity.yaml = """
version: "1.0"
workflow:
  name: test
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: researcher
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: hello
    provider: openai
    model_name: gpt-4o
config: {}
"""
        workflow_repo.get_by_id.return_value = mock_entity
        provider_repo.get_by_type.return_value = None  # No provider

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        with patch.dict("os.environ", {}, clear=False):
            # Remove any OPENAI_API_KEY env var
            import os

            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

            await svc.launch_execution(run_id, "wf_1", {"instruction": "test"})
            await asyncio.sleep(0.1)

            with Session(db_engine) as session:
                updated = session.get(Run, run_id)
                assert updated.status == RunStatus.failed

    @pytest.mark.asyncio
    async def test_launch_failure_before_task_creation_sets_failed(self):
        """If launch_execution fails before creating the async task, Run is set to failed."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_prefail",
            workflow_id="wf_missing",
            workflow_name="wf_missing",
            status=RunStatus.pending,
            task_json="{}",
        )
        run_repo = Mock()
        run_repo.get_run.return_value = run
        workflow_repo = Mock()
        provider_repo = Mock()

        # Workflow not found
        workflow_repo.get_by_id.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        await svc.launch_execution("run_prefail", "wf_missing", {"instruction": "x"})
        await asyncio.sleep(0.05)

        run_repo.update_run.assert_called()
        updated = run_repo.update_run.call_args[0][0]
        assert updated.status == RunStatus.failed

    @pytest.mark.asyncio
    async def test_missing_instruction_in_task_data(self):
        """task_data missing 'instruction' key raises validation error / sets failed."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_noinstr",
            workflow_id="wf_1",
            workflow_name="wf_1",
            status=RunStatus.pending,
            task_json="{}",
        )
        run_repo = Mock()
        run_repo.get_run.return_value = run
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        # task_data has no "instruction" key
        await svc.launch_execution("run_noinstr", "wf_1", {})
        await asyncio.sleep(0.1)

        run_repo.update_run.assert_called()
        updated = run_repo.update_run.call_args[0][0]
        assert updated.status == RunStatus.failed


# ---------------------------------------------------------------------------
# 5. Run status transitions
# ---------------------------------------------------------------------------


class TestRunStatusTransitions:
    @pytest.mark.asyncio
    async def test_run_transitions_to_running(self):
        """After launch_execution, Run.status should transition to running (via observer)."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_trans"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        running_seen = asyncio.Event()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            from runsight_core.state import WorkflowState

            async def slow_run(*a, **kw):
                running_seen.set()
                await asyncio.sleep(0.5)
                return WorkflowState()

            mock_wf = Mock()
            mock_wf.run = slow_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.wait_for(running_seen.wait(), timeout=2.0)

            # Observer should have set status to running in the DB
            with Session(db_engine) as session:
                updated = session.get(Run, run_id)
                assert updated.status in (RunStatus.running, RunStatus.completed)

    @pytest.mark.asyncio
    async def test_run_transitions_to_completed_on_success(self):
        """After workflow.run() succeeds, Run.status = completed (via observer)."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_comp"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            from runsight_core.state import WorkflowState

            result_state = WorkflowState()

            # Mock wf.run to behave like real Workflow.run(): call observer callbacks
            async def _mock_run(state, observer=None):
                if observer:
                    observer.on_workflow_complete("test", state, 0.1)
                return result_state

            mock_wf = Mock()
            mock_wf.run = _mock_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            with Session(db_engine) as session:
                updated = session.get(Run, run_id)
                assert updated.status == RunStatus.completed

    @pytest.mark.asyncio
    async def test_run_transitions_to_failed_on_error(self):
        """After workflow.run() raises, Run.status = failed (via observer)."""
        ExecutionService = _import_execution_service()
        from runsight_api.domain.entities.run import Run, RunStatus

        db_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(db_engine)

        run_id = "run_fail"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                status=RunStatus.pending,
                task_json="{}",
            )
            session.add(run)
            session.commit()

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = VALID_RUNTIME_YAML
        workflow_repo.get_by_id.return_value = mock_entity
        provider = Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        provider_repo.list_all.return_value = [provider]

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            error = RuntimeError("LLM exploded")

            # Mock wf.run to behave like real Workflow.run(): call observer on error, then raise
            async def _mock_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", error, 0.1)
                raise error

            mock_wf = Mock()
            mock_wf.run = _mock_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.1)

            with Session(db_engine) as session:
                updated = session.get(Run, run_id)
                assert updated.status == RunStatus.failed
                assert updated.error is not None


class TestExecutionRuntimeResolution:
    @pytest.mark.asyncio
    async def test_launch_execution_rejects_providerless_modeless_soul_without_workflow_model(self):
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        settings_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = """
version: "1.0"
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: test
souls:
  test:
    id: soul_1
    role: tester
    system_prompt: hello
config: {}
"""
        workflow_repo.get_by_id.return_value = mock_entity
        workflow_repo._get_path.return_value = "/fake/workflows/wf_1.yaml"
        provider_repo.list_all.return_value = []
        settings_repo.get_settings.return_value = Mock(fallback_enabled=False)
        settings_repo.get_fallback_map.return_value = []

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            settings_repo=settings_repo,
        )

        with patch.object(svc, "_fail_run_on_prepare_error") as mock_fail:
            await svc.launch_execution("run_missing_model", "wf_1", {"instruction": "do stuff"})

        mock_fail.assert_called_once()
        assert "explicit provider" in str(mock_fail.call_args.args[1])

    @pytest.mark.asyncio
    async def test_launch_execution_rejects_provider_only_soul_without_model_name(self):
        ExecutionService = _import_execution_service()
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        settings_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = """
version: "1.0"
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: test
souls:
  test:
    id: soul_1
    role: tester
    system_prompt: hello
    provider: openai
config: {}
"""
        workflow_repo.get_by_id.return_value = mock_entity
        workflow_repo._get_path.return_value = "/fake/workflows/wf_1.yaml"
        provider_repo.list_all.return_value = [
            Mock(id="openai", type="openai", is_active=True, models=["gpt-4o"])
        ]
        settings_repo.get_settings.return_value = Mock(fallback_enabled=False)
        settings_repo.get_fallback_map.return_value = []

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            settings_repo=settings_repo,
        )

        with patch.object(svc, "_fail_run_on_prepare_error") as mock_fail:
            await svc.launch_execution(
                "run_missing_model_name", "wf_1", {"instruction": "do stuff"}
            )

        mock_fail.assert_called_once()
        assert "explicit model_name" in str(mock_fail.call_args.args[1])
