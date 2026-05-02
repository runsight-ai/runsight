"""Governance coverage for the node-status enum migration.

Boundary: execution observer and run service must not reintroduce bare node
status string assignments while node writes are still spread across modules.
Owner: API logic owners.
Exit criteria: replace these source checks once node status writes are
centralized behind behavior-only helpers or repository methods.
"""

import inspect


def test_execution_observer_uses_node_status_enum_without_magic_assignments():
    source = inspect.getsource(
        __import__(
            "runsight_api.logic.observers.execution_observer",
            fromlist=["ExecutionObserver"],
        )
    )
    forbidden = [
        'status="running"',
        'status="completed"',
        'status="failed"',
        'status="pending"',
        "status='running'",
        "status='completed'",
        "status='failed'",
        "status='pending'",
    ]

    assert "NodeStatus" in source
    assert [text for text in forbidden if text in source] == []


def test_run_service_uses_node_status_enum_without_magic_comparisons():
    source = inspect.getsource(
        __import__("runsight_api.logic.services.run_service", fromlist=["RunService"])
    )
    forbidden = [
        '== "running"',
        '== "completed"',
        '== "failed"',
        '== "pending"',
        "== 'running'",
        "== 'completed'",
        "== 'failed'",
        "== 'pending'",
    ]

    assert "NodeStatus" in source
    assert [text for text in forbidden if text in source] == []
