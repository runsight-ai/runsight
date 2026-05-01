"""StreamingObserver SSE error redaction behavior."""

from __future__ import annotations

import json

from runsight_api.logic.observers.streaming_observer import StreamingObserver

from sensitive_redaction_helpers import REDACTED, SENSITIVE_VALUE, make_sensitive_state


def test_streaming_observer_redacts_error_sse_payload_when_state_is_available() -> None:
    observer = StreamingObserver(run_id="run_sensitive_api")
    state = make_sensitive_state()

    observer.on_block_error(
        "wf",
        "fail_secret",
        "CodeBlock",
        0.1,
        RuntimeError(f"failed with {SENSITIVE_VALUE}"),
        state=state,
    )

    queued = observer.queue.get_nowait()
    payload = json.dumps(queued, default=str)
    assert queued["event"] == "node_failed"
    assert SENSITIVE_VALUE not in payload
    assert REDACTED in payload


def test_streaming_observer_redacts_workflow_error_sse_payload_when_state_is_available() -> None:
    observer = StreamingObserver(run_id="run_sensitive_api")
    state = make_sensitive_state()

    observer.on_workflow_error(
        "wf",
        RuntimeError(f"workflow failed with {SENSITIVE_VALUE}"),
        0.2,
        state=state,
    )

    queued = observer.queue.get_nowait()
    payload = json.dumps(queued, default=str)
    assert queued["event"] == "run_failed"
    assert SENSITIVE_VALUE not in payload
    assert REDACTED in payload
