"""Legacy sensitive-redaction boundary check.

Focused owner suites now cover execution input prep, workflow input snapshots,
execution observer persistence, streaming observer SSE payloads, and eval
observer persistence/SSE payloads.
"""

from __future__ import annotations

from pathlib import Path


def test_sensitive_redaction_behavior_is_owned_by_focused_suites() -> None:
    logic_tests = Path(__file__).resolve().parent

    assert {
        "test_execution_input_redaction.py",
        "test_workflow_input_snapshot_redaction.py",
        "test_execution_observer_redaction.py",
        "test_streaming_observer_redaction.py",
        "test_eval_observer_redaction.py",
    } <= {path.name for path in logic_tests.glob("test_*_redaction.py")}
