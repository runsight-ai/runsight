"""Plugin registry, not- prefix handling, and assertion dispatchers."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from jsonpath_ng import parse as jp_parse

from runsight_core.assertions import custom as custom_assertions
from runsight_core.assertions.base import (
    AssertionContext,
    GradingResult,
    grading_result_from_data,
)
from runsight_core.assertions.custom import _build_adapter_class
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.isolation.envelope import ContextEnvelope, PromptEnvelope, SoulEnvelope
from runsight_core.isolation.harness import SubprocessHarness

if TYPE_CHECKING:
    from runsight_core.yaml.discovery import AssertionMeta, ScanIndex

_REGISTRY: dict[str, type] = {}

NOT_PREFIX = "not-"


def register_assertion(type_str: str, handler: type) -> None:
    """Register an assertion handler class by type string."""
    _REGISTRY[type_str] = handler


def register_custom_assertions(index: "ScanIndex[AssertionMeta]") -> None:
    """Register custom assertions from a discovery scan index."""
    for meta in index.ids().values():
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


def _build_assertion_envelope(
    *,
    cfg: dict[str, Any],
    output: str,
    context: AssertionContext,
) -> ContextEnvelope:
    """Build an assertion ContextEnvelope for subprocess execution."""
    config = cfg.get("config")
    config_payload = config if isinstance(config, dict) else {}
    judge_soul_raw = config_payload.get("judge_soul")
    judge_soul = judge_soul_raw if isinstance(judge_soul_raw, dict) else {}
    max_tool_iterations = judge_soul.get("max_tool_iterations", 1)
    if not isinstance(max_tool_iterations, int):
        max_tool_iterations = 1

    block_config: dict[str, Any] = {
        "assertion": {
            "type": cfg.get("type", ""),
            "value": cfg.get("value", ""),
            "threshold": cfg.get("threshold"),
            "config": config_payload,
            "metric": cfg.get("metric"),
            "transform": cfg.get("transform"),
        },
        "output_to_grade": output,
        "judge_soul": judge_soul,
    }

    return ContextEnvelope(
        block_id=context.block_id or "assertion",
        block_type="assertion",
        block_config=block_config,
        soul=SoulEnvelope(
            id=str(judge_soul.get("id", "assertion_judge")),
            role=str(judge_soul.get("role", "Assertion Judge")),
            name=str(judge_soul.get("name") or judge_soul.get("role") or "Assertion Judge"),
            system_prompt=str(judge_soul.get("system_prompt", "")),
            model_name=str(judge_soul.get("model_name", "gpt-4o-mini")),
            provider=str(judge_soul.get("provider", "")),
            temperature=judge_soul.get("temperature"),
            max_tokens=judge_soul.get("max_tokens"),
            required_tool_calls=[],
            max_tool_iterations=max_tool_iterations,
        ),
        tools=[],
        prompt=PromptEnvelope(
            id=f"assert-{context.block_id or 'task'}",
            instruction=context.prompt,
            context={},
        ),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )


async def _run_smart_llm_assertion(
    *,
    cfg: dict[str, Any],
    output: str,
    context: AssertionContext,
    api_keys: dict[str, str],
) -> GradingResult:
    """Run an llm_judge assertion through the subprocess harness."""
    harness = SubprocessHarness(api_keys=dict(api_keys))
    envelope = _build_assertion_envelope(cfg=cfg, output=output, context=context)
    result = await harness.run(envelope)

    if result.error:
        raise RuntimeError(result.error)
    if not result.output:
        raise ValueError("smart assertion subprocess returned empty output")

    payload = json.loads(result.output)
    grading = grading_result_from_data(payload)
    if grading.assertion_type is None:
        grading.assertion_type = "llm_judge"

    # Active BudgetSession accounting happens inside the subprocess harness IPC path.
    # Re-accruing result.cost_usd here would double-count the same LLM call.
    return grading


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
    api_keys: dict[str, str] | None = None,
    llm_judge_runner: Callable[
        [dict[str, Any], str, AssertionContext],
        Awaitable[GradingResult],
    ]
    | None = None,
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
            if cfg.get("type") == "llm_judge":
                if llm_judge_runner is not None:
                    result = await llm_judge_runner(cfg, output, context)
                elif api_keys is not None:
                    result = await _run_smart_llm_assertion(
                        cfg=cfg,
                        output=output,
                        context=context,
                        api_keys=api_keys,
                    )
                else:
                    raise ValueError(
                        "llm_judge assertions require engine api_keys or an llm_judge_runner"
                    )
            else:
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
        if cfg.get("type") == "llm_judge":
            raise ValueError(
                "llm_judge assertions require async run_assertions with api_keys or an llm_judge_runner"
            )
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
