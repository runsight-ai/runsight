"""Integration tests for RUN-699 Scenario 2: EvalObserver transform wiring.

Given an EvalObserver with assertion_configs containing a
transform: "json_path:$.result" config for block "analyze",
a RunNode persisted in the DB, and a BlockResult with JSON output,
verifies that:
  - The assertion evaluates against the transformed value, not the raw JSON
  - eval_score is persisted on the RunNode
  - node_eval_complete SSE event is emitted with the assertion result

Pattern follows test_eval_observer.py (RUN-315).
"""

import asyncio

import pytest
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.logic.observers.eval_observer import EvalObserver


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def seed_run(db_engine):
    """Insert a pending Run record and return (engine, run_id)."""
    run_id = "run_699_transform"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_transform",
            workflow_name="transform_workflow",
            status=RunStatus.pending,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return db_engine, run_id


@pytest.fixture
def seed_run_with_node(seed_run):
    """Insert a Run + completed RunNode for block 'analyze'."""
    engine, run_id = seed_run
    with Session(engine) as session:
        node = RunNode(
            id=f"{run_id}:analyze",
            run_id=run_id,
            node_id="analyze",
            block_type="LinearBlock",
            status="completed",
            cost_usd=0.03,
            tokens={"total": 800},
            output='{"result": "success", "extra": "data"}',
        )
        session.add(node)
        session.commit()
    return engine, run_id


@pytest.fixture
def sse_queue():
    """An asyncio.Queue that simulates the StreamingObserver queue."""
    return asyncio.Queue()


@pytest.fixture
def sample_soul():
    """A minimal Soul for testing."""
    return Soul(
        id="analyst_v1",
        kind="soul",
        name="Data Analyst",
        role="Data Analyst",
        system_prompt="You are a data analyst.",
        model_name="gpt-4o",
    )


@pytest.fixture
def sample_state():
    """A WorkflowState with a JSON-output block result for 'analyze'."""
    return WorkflowState(
        total_cost_usd=0.03,
        total_tokens=800,
        results={
            "analyze": BlockResult(output='{"result": "success", "extra": "data"}'),
        },
    )


@pytest.fixture
def transform_contains_success_configs():
    """Assertion config: contains 'success' after json_path:$.result transform."""
    return {
        "analyze": [
            {
                "type": "contains",
                "value": "success",
                "weight": 1.0,
                "transform": "json_path:$.result",
            },
        ],
    }


@pytest.fixture
def transform_contains_extra_configs():
    """Assertion config: contains 'extra' after json_path:$.result transform.

    This should FAIL because json_path:$.result extracts 'success',
    which does not contain 'extra'.
    """
    return {
        "analyze": [
            {
                "type": "contains",
                "value": "extra",
                "weight": 1.0,
                "transform": "json_path:$.result",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Scenario 2: Transform assertion — positive case
# ---------------------------------------------------------------------------


class TestEvalObserverTransformPositive:
    """EvalObserver with transform: json_path:$.result evaluates against
    the extracted value 'success', not the full JSON string."""

    @pytest.mark.asyncio
    async def test_transform_assertion_passes_on_extracted_value(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_success_configs,
    ):
        """contains 'success' with transform json_path:$.result should pass
        because $.result == 'success'."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_success_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_passed is True
            assert node.eval_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_transform_persists_eval_score_on_run_node(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_success_configs,
    ):
        """eval_score is persisted on the RunNode after transform assertion."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_success_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_score is not None

    @pytest.mark.asyncio
    async def test_transform_emits_sse_event(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_success_configs,
    ):
        """node_eval_complete SSE event is emitted with the assertion result."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_success_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        assert not sse_queue.empty()
        event = sse_queue.get_nowait()
        assert event["event"] == "node_eval_complete"
        data = event["data"]
        assert data["node_id"] == "analyze"
        assert "eval_score" in data
        assert "passed" in data
        assert data["passed"] is True

    @pytest.mark.asyncio
    async def test_transform_eval_results_contain_assertion_details(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_success_configs,
    ):
        """eval_results JSON contains assertion details after transform."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_success_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_results is not None
            results = node.eval_results
            assert "assertions" in results
            assertion_list = results["assertions"]
            assert len(assertion_list) >= 1
            first = assertion_list[0]
            assert first["passed"] is True
            assert first["score"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Scenario 2: Transform assertion — negative case
# ---------------------------------------------------------------------------


class TestEvalObserverTransformNegative:
    """EvalObserver with transform: json_path:$.result extracts 'success',
    so assertions checking for values NOT in 'success' should fail."""

    @pytest.mark.asyncio
    async def test_transform_assertion_fails_when_extracted_value_missing_target(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_extra_configs,
    ):
        """contains 'extra' with transform json_path:$.result should FAIL
        because $.result == 'success' which does not contain 'extra'."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_extra_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_passed is False
            assert node.eval_score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_transform_negative_emits_sse_with_failed_result(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_extra_configs,
    ):
        """SSE event is emitted even when the assertion fails after transform."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_extra_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        assert not sse_queue.empty()
        event = sse_queue.get_nowait()
        assert event["event"] == "node_eval_complete"
        data = event["data"]
        assert data["node_id"] == "analyze"
        assert data["passed"] is False

    @pytest.mark.asyncio
    async def test_transform_negative_eval_score_persisted_as_zero(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_extra_configs,
    ):
        """eval_score is persisted as 0.0 on RunNode when transform assertion fails."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_extra_configs,
        )
        obs.on_block_complete(
            "transform_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_score is not None
            assert node.eval_score == pytest.approx(0.0)
