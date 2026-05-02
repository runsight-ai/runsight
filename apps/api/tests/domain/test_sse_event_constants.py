"""Stable SSE event-name contract."""

from runsight_api.domain import events


def test_sse_event_constants_keep_wire_names() -> None:
    assert {
        "SSE_RUN_STARTED": "run_started",
        "SSE_RUN_COMPLETED": "run_completed",
        "SSE_RUN_FAILED": "run_failed",
        "SSE_NODE_STARTED": "node_started",
        "SSE_NODE_COMPLETED": "node_completed",
        "SSE_NODE_FAILED": "node_failed",
    }.items() <= {
        name: getattr(events, name)
        for name in (
            "SSE_RUN_STARTED",
            "SSE_RUN_COMPLETED",
            "SSE_RUN_FAILED",
            "SSE_NODE_STARTED",
            "SSE_NODE_COMPLETED",
            "SSE_NODE_FAILED",
        )
    }.items()


def test_terminal_event_contract_contains_run_terminal_events() -> None:
    assert events.SSE_TERMINAL_EVENTS == (
        events.SSE_RUN_COMPLETED,
        events.SSE_RUN_FAILED,
    )


def test_sse_event_constants_are_plain_strings() -> None:
    for name in (
        "SSE_RUN_STARTED",
        "SSE_RUN_COMPLETED",
        "SSE_RUN_FAILED",
        "SSE_NODE_STARTED",
        "SSE_NODE_COMPLETED",
        "SSE_NODE_FAILED",
    ):
        assert type(getattr(events, name)) is str
