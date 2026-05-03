"""EvalObserver assertion execution and RunNode eval field persistence."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode
from eval_observer_helpers import (
    EVAL_BLOCK_ID,
    EVAL_BLOCK_TYPE,
    EVAL_WORKFLOW_ID,
    EVAL_OUTPUT,
    assertion_configs_for,
    import_eval_observer,
    make_eval_observer_engine,
    make_eval_soul,
    make_eval_sse_queue,
    make_eval_state,
    seed_eval_run_with_node,
)


def _run_observer(assertion_configs, *, state=None):
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=assertion_configs,
    )
    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        state or make_eval_state(),
        soul=make_eval_soul(),
    )
    with Session(engine) as session:
        node = session.get(RunNode, f"{run_id}:{EVAL_BLOCK_ID}")
        return node.eval_score, node.eval_passed, node.eval_results


@pytest.mark.asyncio
async def test_contains_assertion_persists_eval_score() -> None:
    eval_score, _, _ = _run_observer(assertion_configs_for())

    assert eval_score is not None
    assert eval_score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_multiple_assertions_compute_weighted_aggregate_score() -> None:
    eval_score, _, _ = _run_observer(
        assertion_configs_for(
            assertions=[
                {"type": "contains", "value": "Sources", "weight": 2.0},
                {"type": "contains", "value": "information", "weight": 1.0},
            ],
        )
    )

    assert eval_score is not None
    assert eval_score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_failing_assertion_sets_eval_passed_false_and_score_zero() -> None:
    eval_score, eval_passed, _ = _run_observer(
        assertion_configs_for(value="NONEXISTENT_STRING_THAT_WONT_MATCH")
    )

    assert eval_passed is False
    assert eval_score == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_passing_assertion_sets_eval_passed_true() -> None:
    eval_score, eval_passed, _ = _run_observer(assertion_configs_for())

    assert eval_passed is True
    assert eval_score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_eval_results_contain_assertion_details() -> None:
    _, _, eval_results = _run_observer(assertion_configs_for())

    assert eval_results is not None
    assert "assertions" in eval_results
    assertion_list = eval_results["assertions"]
    assert len(assertion_list) >= 1
    first = assertion_list[0]
    assert "type" in first or "assertion_type" in first
    assert "passed" in first
    assert "score" in first
    assert "reason" in first


@pytest.mark.asyncio
async def test_cost_assertion_reads_cost_from_run_node_context() -> None:
    eval_score, eval_passed, _ = _run_observer(
        assertion_configs_for(kind="cost", threshold=0.10),
        state=make_eval_state(output="Output"),
    )

    assert eval_passed is True
    assert eval_score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_cost_assertion_exceeding_threshold_fails() -> None:
    eval_score, eval_passed, _ = _run_observer(
        assertion_configs_for(kind="cost", threshold=0.01),
        state=make_eval_state(output="Output", total_cost_usd=0.50, total_tokens=5000),
    )

    assert eval_passed is False
    assert eval_score == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_assertion_execution_uses_block_output_from_workflow_state() -> None:
    eval_score, eval_passed, _ = _run_observer(
        assertion_configs_for(value="state-only signal"),
        state=make_eval_state(output=f"{EVAL_OUTPUT} with state-only signal"),
    )

    assert eval_passed is True
    assert eval_score == pytest.approx(1.0)
