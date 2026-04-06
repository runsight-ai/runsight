"""Red tests for RUN-717: RunStatus mapping for budget_exceeded terminal state.

When BudgetKilledException propagates out with no error route, the run-tracking
layer must map it to a structured terminal state:
  - RunStatus.failed
  - fail_reason = "budget_exceeded"
  - fail_metadata = {scope, block_id, limit_kind, limit_value, actual_value}

Tests fail because:
  1. Run model lacks fail_reason / fail_metadata fields
  2. ExecutionService._run_workflow() has no BudgetKilledException-specific handling
"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_core.budget_enforcement import BudgetKilledException


# ---------------------------------------------------------------------------
# Part 1: Run model — fail_reason / fail_metadata fields
# ---------------------------------------------------------------------------


class TestRunModelBudgetFields:
    """Verify the Run model exposes fail_reason and fail_metadata."""

    def test_run_has_fail_reason_field(self):
        """Run model must have a fail_reason: Optional[str] field, defaulting to None."""
        run = Run(
            id="run_fr_1",
            workflow_id="wf_1",
            workflow_name="wf_1",
            task_json="{}",
        )
        assert hasattr(run, "fail_reason"), "Run model missing 'fail_reason' field"
        assert run.fail_reason is None, "fail_reason default must be None"

    def test_run_has_fail_metadata_field(self):
        """Run model must have a fail_metadata: Optional[Dict[str, Any]] field, defaulting to None."""
        run = Run(
            id="run_fm_1",
            workflow_id="wf_1",
            workflow_name="wf_1",
            task_json="{}",
        )
        assert hasattr(run, "fail_metadata"), "Run model missing 'fail_metadata' field"
        assert run.fail_metadata is None, "fail_metadata default must be None"

    def test_fail_reason_accepts_string_value(self):
        """fail_reason field accepts an arbitrary string."""
        run = Run(
            id="run_fr_2",
            workflow_id="wf_1",
            workflow_name="wf_1",
            task_json="{}",
            fail_reason="budget_exceeded",
        )
        assert run.fail_reason == "budget_exceeded"

    def test_fail_metadata_accepts_dict_value(self):
        """fail_metadata field accepts a dict with budget details."""
        metadata = {
            "scope": "block",
            "block_id": "b1",
            "limit_kind": "cost_usd",
            "limit_value": 0.5,
            "actual_value": 0.75,
        }
        run = Run(
            id="run_fm_2",
            workflow_id="wf_1",
            workflow_name="wf_1",
            task_json="{}",
            fail_metadata=metadata,
        )
        assert run.fail_metadata == metadata

    def test_fail_metadata_persists_as_json_column(self):
        """fail_metadata must round-trip through SQLite via a JSON column."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        metadata = {
            "scope": "workflow",
            "block_id": None,
            "limit_kind": "token_cap",
            "limit_value": 10000,
            "actual_value": 12345,
        }
        run_id = "run_json_rt"

        with Session(engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                task_json="{}",
                fail_reason="budget_exceeded",
                fail_metadata=metadata,
            )
            session.add(run)
            session.commit()

        with Session(engine) as session:
            loaded = session.get(Run, run_id)
            assert loaded is not None
            assert loaded.fail_reason == "budget_exceeded"
            assert loaded.fail_metadata == metadata
            assert loaded.fail_metadata["scope"] == "workflow"
            assert loaded.fail_metadata["limit_kind"] == "token_cap"

    def test_fail_reason_and_metadata_coexist_with_existing_error_fields(self):
        """fail_reason/fail_metadata work alongside existing error/error_traceback."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_coexist"
        with Session(engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="wf_1",
                task_json="{}",
                status=RunStatus.failed,
                error="Budget limit exceeded on block 'b1': cost_usd=0.75 > cap=0.50",
                error_traceback="Traceback (most recent call last):\n  ...",
                fail_reason="budget_exceeded",
                fail_metadata={
                    "scope": "block",
                    "block_id": "b1",
                    "limit_kind": "cost_usd",
                    "limit_value": 0.5,
                    "actual_value": 0.75,
                },
            )
            session.add(run)
            session.commit()

        with Session(engine) as session:
            loaded = session.get(Run, run_id)
            assert loaded.status == RunStatus.failed
            assert loaded.error is not None
            assert loaded.error_traceback is not None
            assert loaded.fail_reason == "budget_exceeded"
            assert loaded.fail_metadata["block_id"] == "b1"


# ---------------------------------------------------------------------------
# Part 2: ExecutionService._run_workflow — BudgetKilledException handling
# ---------------------------------------------------------------------------

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


def _make_execution_service(engine=None):
    """Create an ExecutionService with mocked repos."""
    from runsight_api.logic.services.execution_service import ExecutionService

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
        engine=engine,
    )
    return svc


def _budget_exception(
    *,
    scope="block",
    block_id="b1",
    limit_kind="cost_usd",
    limit_value=0.50,
    actual_value=0.75,
):
    """Construct a BudgetKilledException with the given parameters."""
    return BudgetKilledException(
        scope=scope,
        block_id=block_id,
        limit_kind=limit_kind,
        limit_value=limit_value,
        actual_value=actual_value,
    )


class TestBudgetExceptionSetsFailReason:
    """When BudgetKilledException propagates from wf.run(), the run record
    must get fail_reason='budget_exceeded' and structured fail_metadata."""

    @pytest.mark.asyncio
    async def test_budget_exception_sets_status_failed(self):
        """BudgetKilledException -> RunStatus.failed."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_budget_status"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        exc = _budget_exception()

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", exc, 0.1)
                raise exc

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed

    @pytest.mark.asyncio
    async def test_budget_exception_sets_fail_reason(self):
        """BudgetKilledException -> fail_reason='budget_exceeded'."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_budget_reason"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        exc = _budget_exception(
            scope="block",
            block_id="b1",
            limit_kind="cost_usd",
            limit_value=0.50,
            actual_value=0.75,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", exc, 0.1)
                raise exc

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.fail_reason == "budget_exceeded"

    @pytest.mark.asyncio
    async def test_budget_exception_sets_fail_metadata_with_all_fields(self):
        """fail_metadata must contain scope, block_id, limit_kind, limit_value, actual_value."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_budget_meta"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        exc = _budget_exception(
            scope="block",
            block_id="b1",
            limit_kind="cost_usd",
            limit_value=0.50,
            actual_value=0.75,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", exc, 0.1)
                raise exc

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            meta = run.fail_metadata
            assert meta is not None, "fail_metadata must be set"
            assert meta["scope"] == "block"
            assert meta["block_id"] == "b1"
            assert meta["limit_kind"] == "cost_usd"
            assert meta["limit_value"] == 0.50
            assert meta["actual_value"] == 0.75

    @pytest.mark.asyncio
    async def test_workflow_scope_budget_exception_metadata(self):
        """Workflow-scope BudgetKilledException populates metadata with scope='workflow'."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_budget_wf_scope"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        exc = _budget_exception(
            scope="workflow",
            block_id=None,
            limit_kind="token_cap",
            limit_value=10000,
            actual_value=12345,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", exc, 0.1)
                raise exc

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            meta = run.fail_metadata
            assert meta is not None
            assert meta["scope"] == "workflow"
            assert meta["block_id"] is None
            assert meta["limit_kind"] == "token_cap"
            assert meta["limit_value"] == 10000
            assert meta["actual_value"] == 12345

    @pytest.mark.asyncio
    async def test_timeout_budget_exception_metadata(self):
        """Timeout-type BudgetKilledException is captured with limit_kind='timeout'."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_budget_timeout"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        exc = _budget_exception(
            scope="block",
            block_id="slow_block",
            limit_kind="timeout",
            limit_value=30.0,
            actual_value=35.2,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", exc, 0.1)
                raise exc

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.fail_reason == "budget_exceeded"
            meta = run.fail_metadata
            assert meta is not None
            assert meta["limit_kind"] == "timeout"
            assert meta["block_id"] == "slow_block"

    @pytest.mark.asyncio
    async def test_generic_exception_does_not_set_fail_reason(self):
        """A non-budget exception must NOT set fail_reason (backward compat)."""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        run_id = "run_generic_exc"
        with Session(engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="wf_1",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        svc = _make_execution_service(engine=engine)
        generic_error = RuntimeError("Something else broke")

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:

            async def _exploding_run(state, observer=None):
                if observer:
                    observer.on_workflow_error("test", generic_error, 0.1)
                raise generic_error

            mock_wf = Mock()
            mock_wf.run = _exploding_run
            mock_parse.return_value = mock_wf

            await svc.launch_execution(run_id, "wf_1", {"instruction": "go"})
            await asyncio.sleep(0.15)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.status == RunStatus.failed
            # Generic errors must NOT set fail_reason or fail_metadata
            assert run.fail_reason is None
            assert run.fail_metadata is None
