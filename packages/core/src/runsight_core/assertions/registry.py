"""Plugin registry, not- prefix handling, and assertion dispatchers."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import TYPE_CHECKING, Any

from jsonpath_ng import parse as jp_parse

from runsight_core.assertions import custom as custom_assertions
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.custom import _build_adapter_class
from runsight_core.assertions.scoring import AssertionsResult

if TYPE_CHECKING:
    from runsight_core.yaml.discovery import AssertionMeta, ScanIndex

_REGISTRY: dict[str, type] = {}

NOT_PREFIX = "not-"


def register_assertion(type_str: str, handler: type) -> None:
    """Register an assertion handler class by type string."""
    _REGISTRY[type_str] = handler


def register_custom_assertions(index: "ScanIndex[AssertionMeta]") -> None:
    """Register custom assertions from a discovery scan index."""
    for meta in index.stems().values():
        if meta.manifest.params is not None:
            custom_assertions._PARAM_SCHEMAS[meta.assertion_id] = meta.manifest.params
        else:
            custom_assertions._PARAM_SCHEMAS.pop(meta.assertion_id, None)
        adapter_class = _build_adapter_class(
            plugin_name=meta.assertion_id,
            code=meta.code or "",
            returns=meta.manifest.returns,
        )
        register_assertion(f"custom:{meta.assertion_id}", adapter_class)


def _get_handler(type_str: str) -> type:
    """Look up a handler by type string. Raises KeyError if not found."""
    if type_str not in _REGISTRY:
        raise KeyError(f"Unknown assertion type: {type_str!r}")
    return _REGISTRY[type_str]


def _apply_transform(transform: str, output: str) -> str | GradingResult:
    """Apply a transform to the output before assertion evaluation.

    Returns the transformed string on success, or a failing GradingResult on error.
    """
    if ":" not in transform:
        return GradingResult(
            passed=False,
            score=0.0,
            reason=f"Unknown transform format: {transform!r}",
            assertion_type="transform",
        )

    kind, path = transform.split(":", 1)

    if kind != "json_path":
        return GradingResult(
            passed=False,
            score=0.0,
            reason=f"Unknown transform type: {kind!r}",
            assertion_type="transform",
        )

    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return GradingResult(
            passed=False,
            score=0.0,
            reason="Transform json_path failed: output is not valid JSON",
            assertion_type="transform",
        )

    expr = jp_parse(path)
    matches = expr.find(data)
    if not matches:
        return GradingResult(
            passed=False,
            score=0.0,
            reason=f"Transform json_path: path {path!r} not found in output",
            assertion_type="transform",
        )

    extracted = matches[0].value
    return str(extracted) if not isinstance(extracted, str) else extracted


def _build_handler(
    handler_cls: type,
    *,
    value: Any,
    threshold: float | None,
    config: dict[str, Any] | None,
) -> Any:
    """Construct a handler using the supported assertion constructor contract."""
    if handler_cls.__init__ is object.__init__:
        return handler_cls()

    parameters = inspect.signature(handler_cls).parameters
    accepts_var_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )

    if not accepts_var_kwargs and "value" not in parameters:
        raise TypeError(
            f"{handler_cls.__name__} must accept a 'value' keyword argument to be used as an assertion"
        )

    kwargs: dict[str, Any] = {"value": value}
    if accepts_var_kwargs or "threshold" in parameters:
        kwargs["threshold"] = threshold
    if accepts_var_kwargs or "config" in parameters:
        kwargs["config"] = config

    return handler_cls(**kwargs)


def run_assertion(
    *,
    type: str,
    output: str,
    context: AssertionContext,
    value: Any = "",
    threshold: float | None = None,
    config: dict[str, Any] | None = None,
    weight: float = 1.0,
    metric: str | None = None,
    transform: str | None = None,
) -> GradingResult:
    """Dispatch a single assertion by type string and return its GradingResult."""
    if transform is not None:
        transformed = _apply_transform(transform, output)
        if isinstance(transformed, GradingResult):
            return transformed
        output = transformed

    negated = type.startswith(NOT_PREFIX)
    base_type = type[len(NOT_PREFIX) :] if negated else type

    handler_cls = _get_handler(base_type)
    handler = _build_handler(handler_cls, value=value, threshold=threshold, config=config)
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
                config=cfg.get("config"),
                weight=weight,
                metric=cfg.get("metric"),
                transform=cfg.get("transform"),
            )
            if cfg.get("metric"):
                result.named_scores[cfg["metric"]] = result.score
            return result, weight

    tasks = [_run_one(cfg) for cfg in config]
    completed = await asyncio.gather(*tasks)

    for result, weight in completed:
        agg.add_result(result, weight=weight)

    return agg


def run_assertions_sync(
    config: list[dict[str, Any]],
    *,
    output: str,
    context: AssertionContext,
) -> AssertionsResult:
    """Run a list of assertion configs synchronously and return aggregated results."""
    agg = AssertionsResult()

    if not config:
        return agg

    for cfg in config:
        weight = cfg.get("weight", 1.0)
        result = run_assertion(
            type=cfg["type"],
            output=output,
            context=context,
            value=cfg.get("value", ""),
            threshold=cfg.get("threshold"),
            config=cfg.get("config"),
            weight=weight,
            metric=cfg.get("metric"),
            transform=cfg.get("transform"),
        )
        if cfg.get("metric"):
            result.named_scores[cfg["metric"]] = result.score
        agg.add_result(result, weight=weight)

    return agg
