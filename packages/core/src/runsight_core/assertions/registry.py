"""Plugin registry, not- prefix handling, and assertion dispatchers."""

from __future__ import annotations

import asyncio
from typing import Any

from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.scoring import AssertionsResult

_REGISTRY: dict[str, type] = {}

NOT_PREFIX = "not-"


def register_assertion(type_str: str, handler: type) -> None:
    """Register an assertion handler class by type string."""
    _REGISTRY[type_str] = handler


def _get_handler(type_str: str) -> type:
    """Look up a handler by type string. Raises KeyError if not found."""
    if type_str not in _REGISTRY:
        raise KeyError(f"Unknown assertion type: {type_str!r}")
    return _REGISTRY[type_str]


def run_assertion(
    *,
    type: str,
    output: str,
    context: AssertionContext,
    value: Any = "",
    threshold: float | None = None,
    weight: float = 1.0,
    metric: str | None = None,
) -> GradingResult:
    """Dispatch a single assertion by type string and return its GradingResult."""
    negated = type.startswith(NOT_PREFIX)
    base_type = type[len(NOT_PREFIX) :] if negated else type

    handler_cls = _get_handler(base_type)
    try:
        handler = handler_cls(value=value)
    except TypeError:
        handler = handler_cls()
    result = handler.evaluate(output, context)

    if negated:
        return GradingResult(
            passed=not result.passed,
            score=1.0 - result.score,
            reason=result.reason,
            named_scores=result.named_scores,
            tokens_used=result.tokens_used,
            component_results=result.component_results,
            assertion_type=result.assertion_type,
            metadata=result.metadata,
        )

    return result


async def run_assertions(
    config: list[dict[str, Any]],
    *,
    output: str,
    context: AssertionContext,
    max_concurrent: int = 10,
) -> AssertionsResult:
    """Run a list of assertion configs concurrently and return aggregated results."""
    agg = AssertionsResult()

    if not config:
        return agg

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_one(cfg: dict[str, Any]) -> tuple[GradingResult, float]:
        async with semaphore:
            weight = cfg.get("weight", 1.0)
            result = run_assertion(
                type=cfg["type"],
                output=output,
                context=context,
                value=cfg.get("value", ""),
                threshold=cfg.get("threshold"),
                weight=weight,
                metric=cfg.get("metric"),
            )
            if cfg.get("metric"):
                result.named_scores[cfg["metric"]] = result.score
            return result, weight

    tasks = [_run_one(cfg) for cfg in config]
    completed = await asyncio.gather(*tasks)

    for result, weight in completed:
        agg.add_result(result, weight=weight)

    return agg
