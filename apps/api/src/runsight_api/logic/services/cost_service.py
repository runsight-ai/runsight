from typing import Dict, Any


class CostService:
    def __init__(self, budget_limit_usd: float = 100.0):
        self.budget_limit_usd = budget_limit_usd

    def aggregate_costs(self, run_nodes: list) -> Dict[str, Any]:
        total_cost = sum(node.cost_usd for node in run_nodes if hasattr(node, "cost_usd"))
        prompt_tokens = sum(
            (node.tokens or {}).get("prompt", 0) for node in run_nodes if hasattr(node, "tokens")
        )
        completion_tokens = sum(
            (node.tokens or {}).get("completion", 0)
            for node in run_nodes
            if hasattr(node, "tokens")
        )
        total_tokens = sum(
            (node.tokens or {}).get("total", 0) for node in run_nodes if hasattr(node, "tokens")
        )

        return {
            "total_cost_usd": total_cost,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def check_budget(self, current_cost: float) -> Dict[str, Any]:
        is_exceeded = current_cost >= self.budget_limit_usd
        return {
            "budget_limit_usd": self.budget_limit_usd,
            "current_cost_usd": current_cost,
            "remaining_budget_usd": max(0.0, self.budget_limit_usd - current_cost),
            "is_exceeded": is_exceeded,
        }
