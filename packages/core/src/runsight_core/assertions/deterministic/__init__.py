"""Deterministic assertion plugins — registers all 15 types on import."""

from runsight_core.assertions.deterministic.linguistic import (
    BleuAssertion,
    LevenshteinAssertion,
    RougeNAssertion,
)
from runsight_core.assertions.deterministic.performance import (
    CostAssertion,
    LatencyAssertion,
)
from runsight_core.assertions.deterministic.string import (
    ContainsAllAssertion,
    ContainsAnyAssertion,
    ContainsAssertion,
    EqualsAssertion,
    IContainsAssertion,
    RegexAssertion,
    StartsWithAssertion,
    WordCountAssertion,
)
from runsight_core.assertions.deterministic.structural import (
    ContainsJsonAssertion,
    IsJsonAssertion,
)
from runsight_core.assertions.registry import register_assertion

_ALL_ASSERTIONS: list[type] = [
    EqualsAssertion,
    ContainsAssertion,
    IContainsAssertion,
    ContainsAllAssertion,
    ContainsAnyAssertion,
    StartsWithAssertion,
    RegexAssertion,
    WordCountAssertion,
    IsJsonAssertion,
    ContainsJsonAssertion,
    CostAssertion,
    LatencyAssertion,
    LevenshteinAssertion,
    BleuAssertion,
    RougeNAssertion,
]

for _cls in _ALL_ASSERTIONS:
    register_assertion(_cls.type, _cls)

__all__ = [
    "BleuAssertion",
    "ContainsAllAssertion",
    "ContainsAnyAssertion",
    "ContainsAssertion",
    "ContainsJsonAssertion",
    "CostAssertion",
    "EqualsAssertion",
    "IContainsAssertion",
    "IsJsonAssertion",
    "LatencyAssertion",
    "LevenshteinAssertion",
    "RegexAssertion",
    "RougeNAssertion",
    "StartsWithAssertion",
    "WordCountAssertion",
]
