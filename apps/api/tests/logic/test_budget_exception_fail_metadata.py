import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.redaction import RunRedactor
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "budget_run_status"


def _prepared_inputs(inputs):
    return PreparedRunInputs(normalized_inputs=inputs, input_redactor=RunRedactor())


def _workflow_fixture(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _make_execution_service(engine):
    from runsight_api.logic.services.execution_service import ExecutionService

    run_repo = RunRepository(Session(engine))
    workflow_repo = Mock()
    workflow_repo.get_by_id.return_value = Mock(
        yaml=_workflow_fixture("valid-runtime-workflow.yaml")
    )
    provider_repo = Mock()
    provider_repo.list_all.return_value = [
        Mock(
            id="fixture-provider",
            type="fixture-provider",
            is_active=True,
            models=["fixture-chat-model"],
        )
    ]
    return ExecutionService(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=engine,
    )


def _seed_run(engine, run_id):
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="budget-workflow",
                workflow_name="Budget workflow",
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


async def _launch_with_error(engine, run_id, exc):
    service = _make_execution_service(engine)
    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:

        async def _exploding_run(state, observer=None, **kwargs):
            if observer:
                observer.on_workflow_error("budgeted-block", exc, 0.1)
            raise exc

        mock_wf = Mock()
        mock_wf.run = _exploding_run
        mock_parse.return_value = mock_wf

        await service.launch_execution(
            run_id,
            "budget-workflow",
            _prepared_inputs({"instruction": "run budget-limited workflow"}),
            branch=None,
        )
        await asyncio.sleep(0.15)


def _budget_exception(
    *,
    scope="block",
    block_id="budgeted-block",
    limit_kind="cost_usd",
    limit_value=0.50,
    actual_value=0.75,
):
    return BudgetKilledException(
        scope=scope,
        block_id=block_id,
        limit_kind=limit_kind,
        limit_value=limit_value,
        actual_value=actual_value,
    )


@pytest.mark.asyncio
async def test_budget_exception_marks_run_failed_with_structured_metadata():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    run_id = "budget-metadata-run"
    _seed_run(engine, run_id)

    await _launch_with_error(engine, run_id, _budget_exception())

    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run.status == RunStatus.failed
        assert run.fail_reason == "budget_exceeded"
        assert run.fail_metadata == {
            "scope": "block",
            "block_id": "budgeted-block",
            "limit_kind": "cost_usd",
            "limit_value": 0.50,
            "actual_value": 0.75,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc, expected",
    [
        (
            _budget_exception(
                scope="workflow",
                block_id=None,
                limit_kind="token_cap",
                limit_value=10000,
                actual_value=12345,
            ),
            {"scope": "workflow", "block_id": None, "limit_kind": "token_cap"},
        ),
        (
            _budget_exception(
                scope="block",
                block_id="slow_block",
                limit_kind="timeout",
                limit_value=30.0,
                actual_value=35.2,
            ),
            {"scope": "block", "block_id": "slow_block", "limit_kind": "timeout"},
        ),
    ],
)
async def test_budget_exception_metadata_preserves_scope_and_limit_kind(exc, expected):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    run_id = f"budget-{expected['limit_kind']}-run"
    _seed_run(engine, run_id)

    await _launch_with_error(engine, run_id, exc)

    with Session(engine) as session:
        meta = session.get(Run, run_id).fail_metadata
        for key, value in expected.items():
            assert meta[key] == value


@pytest.mark.asyncio
async def test_generic_exception_does_not_set_budget_failure_fields():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    run_id = "generic-error-run"
    _seed_run(engine, run_id)

    await _launch_with_error(engine, run_id, RuntimeError("Something else broke"))

    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run.status == RunStatus.failed
        assert run.fail_reason is None
        assert run.fail_metadata is None
