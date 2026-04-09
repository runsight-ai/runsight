"""Helpers for custom assertion plugin adapters."""

from __future__ import annotations

from typing import Any, Callable

from runsight_core.assertions.base import GradingResult


def _custom_assertion_type(plugin_name: str) -> str:
    return f"custom:{plugin_name}"


def _validate_bool_return(raw: Any, plugin_name: str) -> GradingResult:
    if type(raw) is not bool:
        raise TypeError(
            f"Custom assertion {plugin_name!r} declares returns: bool but get_assert returned "
            f"{type(raw).__name__!r}"
        )

    return GradingResult(
        passed=raw,
        score=1.0 if raw else 0.0,
        reason=f"Custom assertion {plugin_name!r} returned {raw}",
        assertion_type=_custom_assertion_type(plugin_name),
    )


def _validate_grading_result_return(raw: Any, plugin_name: str) -> GradingResult:
    if not isinstance(raw, dict):
        raise TypeError(
            f"Custom assertion {plugin_name!r} declares returns: grading_result but get_assert "
            f"returned {type(raw).__name__!r}; expected dict"
        )

    pass_key = next((key for key in ("passed", "pass_", "pass") if key in raw), None)
    if pass_key is None or "score" not in raw:
        actual_keys = sorted(raw.keys())
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result must provide keys "
            f"['passed'|'pass_'|'pass', 'score']; actual keys: {actual_keys}"
        )

    passed = raw[pass_key]
    if type(passed) is not bool:
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result field {pass_key!r} must be bool"
        )

    score = raw["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise TypeError(
            f"Custom assertion {plugin_name!r} grading_result field 'score' must be numeric"
        )
    score = float(score)
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"Custom assertion {plugin_name!r}: score must be between 0.0 and 1.0")

    reason = raw.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)

    return GradingResult(
        passed=passed,
        score=score,
        reason=reason,
        assertion_type=_custom_assertion_type(plugin_name),
    )


_RETURN_VALIDATORS: dict[str, Callable[[Any, str], GradingResult]] = {
    "bool": _validate_bool_return,
    "grading_result": _validate_grading_result_return,
}
