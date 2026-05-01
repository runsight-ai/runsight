"""EvalObserver baseline delta and workflow aggregate behavior."""

from __future__ import annotations

import pytest
from runsight_core.state import WorkflowState
from sqlmodel import Session, select

from runsight_api.domain.entities.run import RunNode, RunStatus
from eval_observer_helpers import (
    EVAL_BLOCK_ID,
    EVAL_BLOCK_TYPE,
    EVAL_OUTPUT,
    EVAL_WORKFLOW_ID,
    assertion_configs_for,
    import_eval_observer,
    make_eval_observer_engine,
    make_eval_soul,
    make_eval_sse_queue,
    make_eval_state,
    seed_eval_baseline_nodes,
    seed_eval_run,
    seed_eval_run_node,
    seed_eval_run_with_node,
)


def _delta_after_block_complete(*, baseline_cost=0.04, baseline_tokens=1200, baseline_score=0.9):
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    soul = make_eval_soul()
    seed_eval_baseline_nodes(
        engine,
        soul,
        cost_usd=baseline_cost,
        tokens_total=baseline_tokens,
        eval_score=baseline_score,
    )
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=sse_queue,
        assertion_configs=assertion_configs_for(),
    )
    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(output=EVAL_OUTPUT, total_cost_usd=0.05, total_tokens=1500),
        soul=soul,
    )
    return sse_queue.get_nowait()["data"]["delta"]


@pytest.mark.asyncio
async def test_delta_contains_cost_pct_tokens_pct_score_delta() -> None:
    delta = _delta_after_block_complete()

    assert "cost_pct" in delta
    assert "tokens_pct" in delta
    assert "score_delta" in delta


@pytest.mark.asyncio
async def test_delta_is_none_when_no_baseline_exists() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=sse_queue,
        assertion_configs=assertion_configs_for(),
    )

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=make_eval_soul(),
    )

    assert sse_queue.get_nowait()["data"]["delta"] is None


@pytest.mark.asyncio
async def test_delta_computation_uses_current_minus_baseline_percent() -> None:
    delta = _delta_after_block_complete(
        baseline_cost=0.04,
        baseline_tokens=1200,
        baseline_score=0.9,
    )

    assert delta["cost_pct"] == pytest.approx(25.0, abs=1.0)
    assert delta["tokens_pct"] == pytest.approx(25.0, abs=1.0)
    assert delta["score_delta"] == pytest.approx(0.1, abs=0.05)


@pytest.mark.asyncio
async def test_delta_is_negative_when_cost_and_tokens_improve() -> None:
    delta = _delta_after_block_complete(
        baseline_cost=0.10,
        baseline_tokens=3000,
        baseline_score=0.8,
    )

    assert delta["cost_pct"] < 0
    assert delta["tokens_pct"] < 0


@pytest.mark.asyncio
async def test_workflow_complete_computes_average_across_evaluated_nodes() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(
        engine,
        run_id="workflow-aggregate-run",
        workflow_name="Eval Aggregate Workflow",
        status=RunStatus.running,
    )
    seed_eval_run_node(engine, run_id=run_id, block_id=EVAL_BLOCK_ID, eval_score=0.8)
    seed_eval_run_node(engine, run_id=run_id, block_id="secondary_eval_block", eval_score=1.0)
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=None,
    )

    obs.on_workflow_complete(EVAL_WORKFLOW_ID, WorkflowState(total_cost_usd=0.10), 5.0)

    with Session(engine) as session:
        nodes = list(
            session.exec(
                select(RunNode).where(RunNode.run_id == run_id, RunNode.eval_score.isnot(None))
            ).all()
        )
    assert len(nodes) == 2
    assert sum(node.eval_score for node in nodes) / len(nodes) == pytest.approx(0.9, abs=0.01)


@pytest.mark.asyncio
async def test_workflow_complete_with_no_eval_nodes_is_noop() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(engine, run_id="workflow-without-eval-nodes-run")
    seed_eval_run_node(engine, run_id=run_id, eval_score=None)
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=None,
    )

    obs.on_workflow_complete(EVAL_WORKFLOW_ID, make_eval_state(), 3.0)


@pytest.mark.asyncio
async def test_workflow_complete_with_single_eval_node_keeps_single_score() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(engine, run_id="single-eval-node-run")
    seed_eval_run_node(engine, run_id=run_id, eval_score=0.75, eval_passed=True)
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=None,
    )

    obs.on_workflow_complete(EVAL_WORKFLOW_ID, make_eval_state(), 3.0)

    with Session(engine) as session:
        node = session.get(RunNode, f"{run_id}:{EVAL_BLOCK_ID}")
        assert node.eval_score == pytest.approx(0.75)
