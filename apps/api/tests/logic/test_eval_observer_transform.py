"""EvalObserver transform wiring.

Given an EvalObserver with assertion_configs containing a
transform: "json_path:$.result" config for block "analyze",
a RunNode persisted in the DB, and a BlockResult with JSON output,
verifies that:
  - The assertion evaluates against the transformed value, not the raw JSON
  - eval_score is persisted on the RunNode
  - node_eval_complete SSE event is emitted with the assertion result

"""

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode
from runsight_api.logic.observers.eval_observer import EvalObserver
from apps.api.tests.logic.eval_observer_helpers import (
    EVAL_TRANSFORM_WORKFLOW_ID,
    transform_contains_extra_configs as _transform_contains_extra_configs_fixture,  # noqa: F401
    transform_contains_success_configs as _transform_contains_success_configs_fixture,  # noqa: F401
    transform_db_engine as _transform_db_engine_fixture,  # noqa: F401
    transform_sample_soul as _sample_soul_fixture,  # noqa: F401
    transform_sample_state as _sample_state_fixture,  # noqa: F401
    transform_seed_run as _transform_seed_run_fixture,  # noqa: F401
    transform_seed_run_with_node as _seed_run_with_node_fixture,  # noqa: F401
    transform_sse_queue as _sse_queue_fixture,  # noqa: F401
)


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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
    so assertions checking for values outside 'success' do not pass."""

    @pytest.mark.asyncio
    async def test_transform_assertion_fails_when_extracted_value_missing_target(
        self,
        seed_run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
        transform_contains_extra_configs,
    ):
        """contains 'extra' does not pass against the transformed value."""
        engine, run_id = seed_run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=transform_contains_extra_configs,
        )
        obs.on_block_complete(
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
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
            EVAL_TRANSFORM_WORKFLOW_ID,
            "analyze",
            "LinearBlock",
            1.0,
            sample_state,
            soul=sample_soul,
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_score is not None
            assert node.eval_score == pytest.approx(0.0)
