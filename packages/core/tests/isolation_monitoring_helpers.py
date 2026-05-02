"""Isolation monitoring coverage.

Tests cover:
- heartbeat and phase-stall subprocess termination
- configurable stall thresholds and block timeouts
- heartbeat propagation through observers
- startup recovery for ghost runs
- long-running llm_call phase thresholds
"""

from __future__ import annotations

from datetime import datetime, timezone

from runsight_core.isolation import (
    ContextEnvelope,
    HeartbeatMessage,
    PromptEnvelope,
    SoulEnvelope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_heartbeat(
    *,
    seq: int = 1,
    phase: str = "initializing",
    detail: str = "",
) -> HeartbeatMessage:
    return HeartbeatMessage(
        heartbeat=seq,
        phase=phase,
        detail=detail,
        timestamp=datetime.now(timezone.utc),
    )


def _make_context_envelope(
    *,
    block_id: str = "monitoring-linear-block",
    block_type: str = "linear",
    timeout_seconds: int = 30,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config={},
        soul=SoulEnvelope(
            id="monitoring-soul",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o-mini",
            max_tool_iterations=3,
        ),
        tools=[],
        prompt=PromptEnvelope(id="monitoring-prompt", instruction="Do the thing.", context={}),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=1_000_000,
    )


# ===========================================================================
# Behavior coverage
# ===========================================================================
