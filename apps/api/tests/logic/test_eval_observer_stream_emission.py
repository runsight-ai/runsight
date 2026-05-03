"""EvalObserver SSE node_eval_complete payload and queue behavior."""

from __future__ import annotations

import pytest

from eval_observer_helpers import (
    EVAL_BLOCK_ID,
    EVAL_BLOCK_TYPE,
    EVAL_WORKFLOW_ID,
    assertion_configs_for,
    import_eval_observer,
    make_eval_observer_engine,
    make_eval_soul,
    make_eval_sse_queue,
    make_eval_state,
    seed_eval_baseline_nodes,
    seed_eval_run_with_node,
)


def _emit_eval_event(*, with_baseline: bool = False):
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    soul = make_eval_soul()
    if with_baseline:
        seed_eval_baseline_nodes(
            engine,
            soul,
            run_id_prefix="previous-baseline-run",
            cost_usd=0.04,
            tokens_total=1200,
            eval_score=0.9,
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
        make_eval_state(),
        soul=soul,
    )
    return sse_queue.get_nowait()


@pytest.mark.asyncio
async def test_on_block_complete_emits_node_eval_complete_event() -> None:
    event = _emit_eval_event()

    assert event["event"] == "node_eval_complete"


@pytest.mark.asyncio
async def test_sse_event_contains_eval_score_passed_and_node_id() -> None:
    event = _emit_eval_event()
    data = event["data"]

    assert data["node_id"] == EVAL_BLOCK_ID
    assert "eval_score" in data
    assert "passed" in data


@pytest.mark.asyncio
async def test_sse_event_contains_assertion_result_payload() -> None:
    event = _emit_eval_event()
    assertions = event["data"]["assertions"]

    assert len(assertions) >= 1
    assert "type" in assertions[0] or "assertion_type" in assertions[0]
    assert assertions[0]["passed"] is True
    assert assertions[0]["score"] == pytest.approx(1.0)
    assert "reason" in assertions[0]


@pytest.mark.asyncio
async def test_sse_event_contains_delta_when_baseline_exists() -> None:
    event = _emit_eval_event(with_baseline=True)
    data = event["data"]

    assert data["delta"] is not None
    delta = data["delta"]
    assert "cost_pct" in delta
    assert "tokens_pct" in delta
    assert "score_delta" in delta


@pytest.mark.asyncio
async def test_sse_event_delta_is_none_when_no_baseline_exists() -> None:
    event = _emit_eval_event()

    assert "delta" in event["data"]
    assert event["data"]["delta"] is None
