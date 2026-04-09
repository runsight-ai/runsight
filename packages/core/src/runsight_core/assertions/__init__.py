"""Assertion plugin interface for runsight_core."""

from runsight_core.assertions.base import (
    Assertion,
    AssertionContext,
    GradingResult,
    TokenUsage,
)
from runsight_core.assertions.registry import (
    register_assertion,
    run_assertion,
    run_assertions,
    run_assertions_sync,
)
from runsight_core.assertions.scoring import AssertionsResult

__all__ = [
    "Assertion",
    "AssertionContext",
    "AssertionsResult",
    "GradingResult",
    "TokenUsage",
    "register_assertion",
    "run_assertion",
    "run_assertions",
    "run_assertions_sync",
]
