"""Deterministic string assertion plugins.

Covers: equals, contains, icontains, contains-all, contains-any,
starts-with, regex, word-count.
"""

from __future__ import annotations

import json
import re
from typing import Any

from runsight_core.assertions.base import AssertionContext, GradingResult


class EqualsAssertion:
    """Exact string match, or explicit JSON deep-equal when configured."""

    type = "equals"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = value
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        value_str = str(self.value)
        if self.config is not None and not isinstance(self.config, dict):
            return GradingResult(
                passed=False,
                score=0.0,
                reason="equals config must be a mapping when provided",
            )

        mode = self.config.get("mode", "string") if self.config else "string"
        if mode == "json":
            try:
                output_parsed = json.loads(output)
                value_parsed = json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                return GradingResult(
                    passed=False,
                    score=0.0,
                    reason="JSON comparison failed: output or expected value is not valid JSON",
                )

            if output_parsed == value_parsed:
                return GradingResult(
                    passed=True, score=1.0, reason="Output matches expected value (JSON deep-equal)"
                )
            return GradingResult(
                passed=False,
                score=0.0,
                reason=f"JSON values differ: expected {value_str!r}, got {output!r}",
            )

        if mode != "string":
            return GradingResult(
                passed=False,
                score=0.0,
                reason=f"Unsupported equals mode: {mode!r}",
            )

        if output == value_str:
            return GradingResult(
                passed=True, score=1.0, reason="Output exactly matches expected value"
            )
        return GradingResult(
            passed=False, score=0.0, reason=f"Expected {value_str!r}, got {output!r}"
        )


class ContainsAssertion:
    """Case-sensitive substring check."""

    type = "contains"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        if self.value in output:
            return GradingResult(passed=True, score=1.0, reason=f"Output contains {self.value!r}")
        return GradingResult(
            passed=False, score=0.0, reason=f"Output does not contain {self.value!r}"
        )


class IContainsAssertion:
    """Case-insensitive substring check."""

    type = "icontains"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        if self.value.lower() in output.lower():
            return GradingResult(
                passed=True, score=1.0, reason=f"Output contains {self.value!r} (case-insensitive)"
            )
        return GradingResult(
            passed=False,
            score=0.0,
            reason=f"Output does not contain {self.value!r} (case-insensitive)",
        )


class ContainsAllAssertion:
    """All items in value list must be substrings."""

    type = "contains-all"

    def __init__(
        self,
        value: Any = None,
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value: list[str] = value if value is not None else []
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        missing = [item for item in self.value if str(item) not in output]
        if not missing:
            return GradingResult(
                passed=True, score=1.0, reason="Output contains all required substrings"
            )
        return GradingResult(passed=False, score=0.0, reason=f"Output missing: {missing!r}")


class ContainsAnyAssertion:
    """At least one item in value list must be a substring."""

    type = "contains-any"

    def __init__(
        self,
        value: Any = None,
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value: list[str] = value if value is not None else []
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        if not self.value:
            return GradingResult(passed=False, score=0.0, reason="No candidates provided to match")
        for item in self.value:
            if str(item) in output:
                return GradingResult(passed=True, score=1.0, reason=f"Output contains {item!r}")
        return GradingResult(
            passed=False, score=0.0, reason=f"Output does not contain any of {self.value!r}"
        )


class StartsWithAssertion:
    """String prefix check."""

    type = "starts-with"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        if output.startswith(self.value):
            return GradingResult(
                passed=True, score=1.0, reason=f"Output starts with {self.value!r}"
            )
        return GradingResult(
            passed=False, score=0.0, reason=f"Output does not start with {self.value!r}"
        )


class RegexAssertion:
    """Regex search match."""

    type = "regex"

    def __init__(
        self,
        value: Any = "",
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = str(value)
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        try:
            if re.search(self.value, output):
                return GradingResult(
                    passed=True, score=1.0, reason=f"Output matches pattern {self.value!r}"
                )
            return GradingResult(
                passed=False, score=0.0, reason=f"Output does not match pattern {self.value!r}"
            )
        except re.error as e:
            return GradingResult(passed=False, score=0.0, reason=f"Invalid regex pattern: {e}")


class WordCountAssertion:
    """Word count check: exact int or {min, max} range."""

    type = "word-count"

    def __init__(
        self,
        value: Any = None,
        threshold: float | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.value = value
        self.threshold = threshold
        self.config = config

    def evaluate(self, output: str, context: AssertionContext) -> GradingResult:
        words = output.split()
        count = len(words)

        if isinstance(self.value, int):
            if count == self.value:
                return GradingResult(
                    passed=True, score=1.0, reason=f"Word count is {count} (expected {self.value})"
                )
            return GradingResult(
                passed=False, score=0.0, reason=f"Word count is {count}, expected {self.value}"
            )

        if isinstance(self.value, dict):
            min_val = self.value.get("min")
            max_val = self.value.get("max")

            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError(f"min ({min_val}) is greater than max ({max_val})")

            if min_val is not None and count < min_val:
                return GradingResult(
                    passed=False, score=0.0, reason=f"Word count {count} is below minimum {min_val}"
                )
            if max_val is not None and count > max_val:
                return GradingResult(
                    passed=False, score=0.0, reason=f"Word count {count} exceeds maximum {max_val}"
                )
            return GradingResult(
                passed=True, score=1.0, reason=f"Word count {count} is within range"
            )

        raise TypeError(f"Invalid value type for word-count: {type(self.value).__name__}")
