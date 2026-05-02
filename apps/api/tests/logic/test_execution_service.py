"""ExecutionService launch-to-runtime smoke coverage."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.logic.services.execution_service import ExecutionService, PreparedRunInputs
from runsight_core.redaction import RunRedactor
from runsight_core.state import BlockResult, WorkflowState


WORKFLOW_ID = "execution-service-smoke"
WORKFLOW_YAML = f"""
version: "1.0"
id: {WORKFLOW_ID}
kind: workflow
workflow:
  id: {WORKFLOW_ID}
  kind: workflow
  name: Execution Service Smoke
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
    system_prompt: hello
    provider: openai
    model_name: gpt-4o
config: {{}}
"""


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=WORKFLOW_ID,
                workflow_name="Execution Service Smoke",
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


def _prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


def _provider() -> Mock:
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.api_key = None
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


@pytest.mark.asyncio
async def test_launch_execution_schedules_runtime_and_persists_success_smoke() -> None:
    engine = _engine()
    run_id = "execution-service-run"
    _seed_run(engine, run_id)

    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = SimpleNamespace(yaml=WORKFLOW_YAML)
    workflow_repo._get_path.return_value = f"/isolated/custom/workflows/{WORKFLOW_ID}.yaml"
    workflow_repo.base_path = "/isolated"
    workflow_repo.build_runnable_workflow_registry.return_value = None
    provider_repo = Mock()
    provider_repo.list_all.return_value = [_provider()]

    repo_session = Session(engine)
    service = ExecutionService(
        run_repo=RunRepository(repo_session),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=engine,
    )
    release = asyncio.Event()
    workflow_started = asyncio.Event()

    async def _run(state: WorkflowState, observer=None, inputs=None):
        assert inputs == {"instruction": "summarize"}
        observer.on_workflow_start("execution-service-smoke", state)
        observer.on_block_start("execution-service-smoke", "analyze", "LinearBlock")
        workflow_started.set()
        await release.wait()
        done_state = state.model_copy(
            update={
                "total_cost_usd": 0.03,
                "total_tokens": 11,
                "results": {"analyze": BlockResult(output="service smoke complete")},
            }
        )
        observer.on_block_complete(
            "execution-service-smoke",
            "analyze",
            "LinearBlock",
            0.2,
            done_state,
        )
        observer.on_workflow_complete("execution-service-smoke", done_state, 0.4)
        return done_state

    workflow = Mock()
    workflow.run = _run

    try:
        with (
            patch.object(service, "_get_workflow_commit_sha", return_value="a" * 40),
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml",
                return_value=workflow,
            ),
        ):
            await service.launch_execution(
                run_id,
                WORKFLOW_ID,
                _prepared_inputs({"instruction": "summarize"}),
            )
            assert run_id in service._runtime.running_tasks
            await asyncio.wait_for(workflow_started.wait(), timeout=1.0)
            release.set()
            await asyncio.wait_for(service._runtime.running_tasks[run_id], timeout=1.0)
            await asyncio.sleep(0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            node = session.get(RunNode, f"{run_id}:analyze")

        assert run.status == RunStatus.completed
        assert run.commit_sha == "a" * 40
        assert node.status == "completed"
        assert node.output == "service smoke complete"
        assert run_id not in service._runtime.running_tasks
    finally:
        release.set()
        repo_session.close()
