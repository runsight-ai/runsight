"""Comprehensive unit tests for CostService.

Tests document current behavior as guardrails — they break on any behavioral change.
"""

from unittest.mock import Mock


from runsight_api.logic.services.cost_service import CostService


# --- aggregate_costs ---


def test_aggregate_costs_normal_nodes():
    """aggregate_costs sums cost_usd and tokens across valid nodes."""
    service = CostService(budget_limit_usd=10.0)

    n1 = Mock(cost_usd=2.5, tokens={"prompt": 100, "completion": 200, "total": 300})
    n2 = Mock(cost_usd=3.0, tokens={"prompt": 50, "completion": 150, "total": 200})

    result = service.aggregate_costs([n1, n2])

    assert result["total_cost_usd"] == 5.5
    assert result["prompt_tokens"] == 150
    assert result["completion_tokens"] == 350
    assert result["total_tokens"] == 500


def test_aggregate_costs_empty_list_returns_zeros():
    """aggregate_costs returns zeros when given empty list."""
    service = CostService(budget_limit_usd=10.0)

    result = service.aggregate_costs([])

    assert result["total_cost_usd"] == 0.0
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0
    assert result["total_tokens"] == 0


def test_aggregate_costs_nodes_without_cost_usd_skipped():
    """Nodes without cost_usd attr are skipped (hasattr check)."""
    service = CostService(budget_limit_usd=10.0)

    n1 = Mock(spec=["tokens"])  # no cost_usd
    n1.tokens = {"prompt": 10, "completion": 20, "total": 30}
    n2 = Mock(cost_usd=1.0, tokens={"prompt": 5, "completion": 5, "total": 10})

    result = service.aggregate_costs([n1, n2])

    assert result["total_cost_usd"] == 1.0  # only n2
    assert result["total_tokens"] == 40


def test_aggregate_costs_nodes_without_tokens_skipped():
    """Nodes without tokens attr are skipped for token aggregates."""
    service = CostService(budget_limit_usd=10.0)

    n1 = Mock(cost_usd=1.0, tokens={"prompt": 100, "completion": 100, "total": 200})
    n2 = Mock(spec=["cost_usd"])  # no tokens
    n2.cost_usd = 2.0

    result = service.aggregate_costs([n1, n2])

    assert result["total_cost_usd"] == 3.0
    assert result["prompt_tokens"] == 100  # only n1
    assert result["completion_tokens"] == 100
    assert result["total_tokens"] == 200


def test_aggregate_costs_mixed_valid_invalid_nodes():
    """Mixed valid/invalid nodes: only valid ones contribute."""
    service = CostService(budget_limit_usd=10.0)

    valid = Mock(cost_usd=2.0, tokens={"prompt": 10, "completion": 20, "total": 30})
    no_cost = Mock(spec=["tokens"])
    no_cost.tokens = {"prompt": 5, "completion": 5, "total": 10}
    no_tokens = Mock(spec=["cost_usd"])
    no_tokens.cost_usd = 1.0

    result = service.aggregate_costs([valid, no_cost, no_tokens])

    assert result["total_cost_usd"] == 3.0  # valid + no_tokens
    assert result["total_tokens"] == 40  # valid + no_cost (no_cost has tokens)


def test_aggregate_costs_tokens_none_treated_as_empty():
    """Nodes with tokens=None use empty dict fallback (total/prompt/completion 0)."""
    service = CostService(budget_limit_usd=10.0)

    n = Mock(cost_usd=1.0, tokens=None)

    result = service.aggregate_costs([n])

    assert result["total_cost_usd"] == 1.0
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0
    assert result["total_tokens"] == 0


# --- check_budget ---


def test_check_budget_under_budget():
    """check_budget: under limit → is_exceeded=False, positive remaining."""
    service = CostService(budget_limit_usd=10.0)

    result = service.check_budget(3.0)

    assert result["budget_limit_usd"] == 10.0
    assert result["current_cost_usd"] == 3.0
    assert result["remaining_budget_usd"] == 7.0
    assert result["is_exceeded"] is False


def test_check_budget_over_budget():
    """check_budget: over limit → is_exceeded=True, remaining=0."""
    service = CostService(budget_limit_usd=10.0)

    result = service.check_budget(15.0)

    assert result["is_exceeded"] is True
    assert result["remaining_budget_usd"] == 0.0
    assert result["current_cost_usd"] == 15.0


def test_check_budget_exact_boundary():
    """check_budget: current_cost >= limit → is_exceeded=True (boundary inclusive)."""
    service = CostService(budget_limit_usd=10.0)

    result = service.check_budget(10.0)

    assert result["is_exceeded"] is True
    assert result["remaining_budget_usd"] == 0.0


def test_check_budget_zero_budget():
    """check_budget: zero budget with any positive cost → exceeded."""
    service = CostService(budget_limit_usd=0.0)

    result = service.check_budget(0.0)

    assert result["is_exceeded"] is True
    assert result["remaining_budget_usd"] == 0.0


def test_check_budget_negative_cost():
    """check_budget: negative cost results in remaining > limit."""
    service = CostService(budget_limit_usd=10.0)

    result = service.check_budget(-5.0)

    assert result["is_exceeded"] is False
    assert result["remaining_budget_usd"] == 15.0
    assert result["current_cost_usd"] == -5.0
