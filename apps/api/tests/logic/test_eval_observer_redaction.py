"""EvalObserver persisted result and SSE redaction behavior."""

from __future__ import annotations

import json

from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode
from runsight_api.logic.observers.eval_observer import EvalObserver

from sensitive_redaction_helpers import (
    REDACTED,
    SENSITIVE_VALUE,
    make_sensitive_eval_db_engine,
    make_sensitive_redactor,
    make_sensitive_sse_queue,
    seed_sensitive_eval_run,
)


def test_eval_observer_redacts_registered_sensitive_values_in_persisted_eval_results_and_sse() -> (
    None
):
    engine = make_sensitive_eval_db_engine()
    seed_sensitive_eval_run(engine)
    sse_queue = make_sensitive_sse_queue()
    state = WorkflowState(
        input_redactor=make_sensitive_redactor(SENSITIVE_VALUE),
        results={
            "block_a": BlockResult(output=f"payload {SENSITIVE_VALUE}"),
        },
    )
    observer = EvalObserver(
        engine=engine,
        run_id="run_sensitive_eval",
        sse_queue=sse_queue,
        assertion_configs={
            "block_a": [
                {"type": "contains", "value": SENSITIVE_VALUE, "weight": 1.0},
            ]
        },
    )

    observer.on_block_complete("wf", "block_a", "LinearBlock", 0.1, state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_sensitive_eval:block_a")

    assert node is not None
    assert node.eval_results is not None
    persisted = json.dumps(node.eval_results, default=str)
    assert SENSITIVE_VALUE not in persisted
    assert REDACTED in persisted
    assert node.eval_results["assertions"][0]["reason"] == f"Output contains '{REDACTED}'"

    event = sse_queue.get_nowait()
    event_payload = json.dumps(event, default=str)
    assert event["event"] == "node_eval_complete"
    assert SENSITIVE_VALUE not in event_payload
    assert REDACTED in event_payload
    assert event["data"]["assertions"][0]["reason"] == f"Output contains '{REDACTED}'"
