"""Fixture builders for dashboard attention transport tests."""

from __future__ import annotations

import time
from unittest.mock import Mock

from runsight_api.transport.schemas.dashboard import AttentionItem


def make_mock_node(
    *,
    node_id: str = "analyze",
    run_id: str = "attention-empty-run",
    soul_id: str = "researcher_v1",
    soul_version: str = "sha256:abc",
    eval_score: float | None = 0.95,
    eval_passed: bool | None = True,
    cost_usd: float = 0.005,
    tokens: dict | None = None,
    eval_results: dict | None = None,
) -> Mock:
    """Create a mock RunNode with eval fields populated."""
    node = Mock()
    node.node_id = node_id
    node.run_id = run_id
    node.soul_id = soul_id
    node.soul_version = soul_version
    node.eval_score = eval_score
    node.eval_passed = eval_passed
    node.cost_usd = cost_usd
    node.tokens = tokens or {"prompt": 100, "completion": 50, "total": 150}
    node.eval_results = eval_results
    node.created_at = time.time()
    return node


def make_attention_service(items: list[AttentionItem] | None = None) -> Mock:
    service = Mock()
    service.get_attention_items.return_value = items or []
    return service


def make_attention_item(
    *,
    type: str,
    title: str,
    description: str = "Attention item description",
    run_id: str = "attention-run",
    workflow_id: str = "attention-workflow",
    severity: str = "warning",
) -> AttentionItem:
    return AttentionItem(
        type=type,
        title=title,
        description=description,
        run_id=run_id,
        workflow_id=workflow_id,
        severity=severity,
    )


def make_cost_spike_items(count: int) -> list[AttentionItem]:
    return [
        make_attention_item(
            type="cost_spike",
            title=f"Cost spike #{index}",
            description=f"Attention item {index}",
            run_id=f"attention-run-{index:03d}",
        )
        for index in range(count)
    ]


def make_assertion_regression_items(count: int) -> list[AttentionItem]:
    return [
        make_attention_item(
            type="assertion_regression",
            title="Assertion regression",
            run_id=f"attention-run-{index:03d}",
        )
        for index in range(count)
    ]
