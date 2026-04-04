"""
Standalone condition evaluation engine.

Extracted from ConditionalBlock to be reusable across any block type.
Evaluates conditions against a block's own result data (no eval_source).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Operator constants
# ---------------------------------------------------------------------------

STRING_OPS = {
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "is_empty",
    "not_empty",
    "regex",
}
NUMERIC_OPS = {"eq", "neq", "gt", "lt", "gte", "lte"}
UNIVERSAL_OPS = {"exists", "not_exists"}

ALL_OPERATORS = STRING_OPS | NUMERIC_OPS | UNIVERSAL_OPS


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Condition:
    """A single condition to evaluate against block result data."""

    eval_key: str
    operator: str
    value: Any = None


@dataclass
class ConditionGroup:
    """A group of conditions combined with AND/OR logic."""

    conditions: List[Condition] = field(default_factory=list)
    combinator: str = "and"


@dataclass
class Case:
    """A named case with a condition group. First match wins."""

    case_id: str
    condition_group: ConditionGroup = field(default_factory=ConditionGroup)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_dotted_path(obj: Any, path: str) -> Any:
    """Resolve a dot-separated key path into a nested dict.

    Args:
        obj: The dict (or nested dict) to resolve into.
        path: Dot-separated key path, e.g. "response.status".

    Returns:
        The resolved value, or None if any segment is missing or
        an intermediate value is not a dict.
    """
    if not isinstance(obj, dict):
        return None
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _key_exists(obj: Any, path: str) -> bool:
    """Check whether a dotted key path exists in obj (even if value is None)."""
    if not isinstance(obj, dict):
        return False
    parts = path.split(".")
    current = obj
    for i, part in enumerate(parts):
        if not isinstance(current, dict):
            return False
        if part not in current:
            return False
        if i < len(parts) - 1:
            current = current[part]
    return True


# ---------------------------------------------------------------------------
# Numeric coercion
# ---------------------------------------------------------------------------


def _coerce_numeric(value: Any, warnings: Optional[List[str]] = None) -> Optional[float]:
    """Try to coerce a value to float. Returns None on failure, appends warning."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        if warnings is not None:
            warnings.append(f"Cannot coerce {value!r} to numeric")
        return None


# ---------------------------------------------------------------------------
# Single condition evaluation
# ---------------------------------------------------------------------------


def evaluate_condition(
    condition: Condition,
    data: Any,
    warnings: Optional[List[str]] = None,
) -> bool:
    """Evaluate a single condition against data.

    Args:
        condition: The condition to evaluate.
        data: The block result data (dict, JSON string, or raw value).
              If a JSON string, it is auto-parsed to a dict.
        warnings: Optional list to collect non-fatal warnings (e.g. coercion issues).

    Returns:
        True if the condition is satisfied, False otherwise.

    Raises:
        ValueError: For unknown operators or invalid regex patterns.
    """
    if warnings is None:
        warnings = []

    # Auto-parse JSON strings
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            pass  # Leave as raw string

    op = condition.operator

    if op not in ALL_OPERATORS:
        raise ValueError(f"Unknown operator: {op!r}")

    # --- Universal operators (key presence, not value) ---
    if op == "exists":
        if isinstance(data, dict):
            return _key_exists(data, condition.eval_key)
        return False

    if op == "not_exists":
        if isinstance(data, dict):
            return not _key_exists(data, condition.eval_key)
        return True

    # --- Resolve the actual value ---
    if isinstance(data, dict):
        actual = resolve_dotted_path(data, condition.eval_key)
    else:
        actual = data  # raw non-dict, non-JSON value

    expected = condition.value

    # --- String operators ---
    if op == "equals":
        return str(actual) == str(expected) if actual is not None else False

    if op == "not_equals":
        return str(actual) != str(expected) if actual is not None else True

    if op == "contains":
        return str(expected) in str(actual) if actual is not None else False

    if op == "not_contains":
        return str(expected) not in str(actual) if actual is not None else True

    if op == "starts_with":
        return str(actual).startswith(str(expected)) if actual is not None else False

    if op == "ends_with":
        return str(actual).endswith(str(expected)) if actual is not None else False

    if op == "is_empty":
        return actual is None or str(actual) == ""

    if op == "not_empty":
        return actual is not None and str(actual) != ""

    if op == "regex":
        if actual is None:
            return False
        try:
            return bool(re.search(str(expected), str(actual)))
        except re.error as e:
            raise ValueError(f"Regex pattern error: {e}")

    # --- Numeric operators ---
    if op in NUMERIC_OPS:
        num_actual = _coerce_numeric(actual, warnings)
        num_expected = _coerce_numeric(expected, warnings)

        if num_actual is None or num_expected is None:
            return False

        if op == "eq":
            return num_actual == num_expected
        if op == "neq":
            return num_actual != num_expected
        if op == "gt":
            return num_actual > num_expected
        if op == "lt":
            return num_actual < num_expected
        if op == "gte":
            return num_actual >= num_expected
        if op == "lte":
            return num_actual <= num_expected

    # Should not be reachable since we check ALL_OPERATORS above
    raise ValueError(f"Unsupported operator: {op!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Condition group evaluation
# ---------------------------------------------------------------------------


def evaluate_condition_group(
    group: ConditionGroup,
    data: Any,
    warnings: Optional[List[str]] = None,
) -> bool:
    """Evaluate a group of conditions with AND/OR combinator.

    Args:
        group: The condition group to evaluate.
        data: The block result data.
        warnings: Optional list to collect warnings.

    Returns:
        True if the group is satisfied according to its combinator.

    Raises:
        ValueError: For unknown combinators.
    """
    if warnings is None:
        warnings = []

    if group.combinator == "and":
        return all(evaluate_condition(c, data, warnings) for c in group.conditions)
    elif group.combinator == "or":
        return any(evaluate_condition(c, data, warnings) for c in group.conditions)
    else:
        raise ValueError(f"Unknown combinator: {group.combinator!r}")


# ---------------------------------------------------------------------------
# Top-level output conditions evaluation
# ---------------------------------------------------------------------------


def evaluate_output_conditions(
    cases: List[Case],
    block_result: Any,
    default: str = "default",
) -> Tuple[str, List[str]]:
    """Evaluate output conditions against a block's result.

    Implements first-match-wins semantics: iterates through cases in order,
    returning the case_id of the first case whose condition_group passes.

    If block_result is a JSON string, it is auto-parsed before evaluation.

    Args:
        cases: Ordered list of Case objects to evaluate.
        block_result: The raw block result (string, dict, etc.).
        default: Decision string to return if no case matches.

    Returns:
        Tuple of (decision_string, warnings_list).
    """
    warnings: List[str] = []

    # Auto-parse JSON strings at the top level
    data = block_result
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            pass

    for case in cases:
        if evaluate_condition_group(case.condition_group, data, warnings):
            return case.case_id, warnings

    return default, warnings
