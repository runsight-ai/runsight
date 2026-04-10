"""Deterministic structural assertion plugins.

Covers: is-json, contains-json.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema

from runsight_core.assertions.base import AssertionContext, GradingResult


class IsJsonAssertion:
    """Validate that the output is valid JSON, with optional JSON Schema validation."""

    type = "is-json"

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
        try:
            parsed = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return GradingResult(passed=False, score=0.0, reason="Output is not valid JSON")

        if self.value is not None:
            try:
                jsonschema.validate(instance=parsed, schema=self.value)
            except jsonschema.ValidationError as e:
                return GradingResult(
                    passed=False, score=0.0, reason=f"JSON Schema validation failed: {e.message}"
                )

        return GradingResult(passed=True, score=1.0, reason="Output is valid JSON")


class ContainsJsonAssertion:
    """Find a valid JSON substring in the output, with optional schema validation."""

    type = "contains-json"

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
        parsed = _extract_json(output)
        if parsed is None:
            return GradingResult(passed=False, score=0.0, reason="No valid JSON found in output")

        if self.value is not None:
            try:
                jsonschema.validate(instance=parsed, schema=self.value)
            except jsonschema.ValidationError as e:
                return GradingResult(
                    passed=False, score=0.0, reason=f"Extracted JSON fails schema: {e.message}"
                )

        return GradingResult(passed=True, score=1.0, reason="Output contains valid JSON")


def _extract_json(text: str) -> Any:
    """Try to extract a JSON object or array from text.

    Scans for '{' and '[' delimiters and attempts to parse from each.
    Returns the first successfully parsed value, or None.
    """
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = 0
        while True:
            idx = text.find(start_char, start)
            if idx == -1:
                break
            # Try parsing from this position to each matching end char
            end = len(text)
            while end > idx:
                try:
                    candidate = text[idx:end]
                    if candidate.rstrip()[-1:] not in (end_char,):
                        end -= 1
                        continue
                    return json.loads(candidate)
                except (json.JSONDecodeError, IndexError):
                    end -= 1
            start = idx + 1
    return None
