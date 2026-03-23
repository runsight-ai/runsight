"""
Data models, TokenCounter protocol, and budget utilities for context windowing.

NOTE: This module must NOT import litellm or tiktoken directly.
TokenCounter is a Protocol — implementations are injected at call sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from runsight_core.memory.windowing import get_model_info


@runtime_checkable
class TokenCounter(Protocol):
    """Callable that counts tokens for a given text and model."""

    def __call__(self, text: str, model: str) -> int: ...


class ContextBudgetRequest(BaseModel):
    """Request payload for context budget computation."""

    model: str
    system_prompt: str
    instruction: str
    context: str
    conversation_history: list[dict]
    output_token_reserve: Optional[int] = None
    budget_ratio: float = Field(default=0.9)


@dataclass
class BudgetReport:
    """Diagnostic report produced after budget allocation."""

    model: str
    max_input_tokens: int
    output_reserve: int
    effective_budget: int
    p1_tokens: int
    p2_tokens_before: int
    p2_tokens_after: int
    p3_tokens_before: int
    p3_tokens_after: int
    p3_pairs_dropped: int
    total_tokens: int
    headroom: int
    warnings: list[str]


@dataclass
class BudgetedContext:
    """Result of budget allocation: the task, messages, and diagnostic report."""

    task: object
    messages: list[dict]
    report: BudgetReport


class ContextBudgetExceeded(Exception):
    """Raised when P1 tokens alone exceed the effective budget."""

    def __init__(self, *, p1_tokens: int, effective_budget: int, model: str) -> None:
        self.p1_tokens = p1_tokens
        self.effective_budget = effective_budget
        self.model = model
        super().__init__(
            f"P1 tokens ({p1_tokens}) exceed effective budget "
            f"({effective_budget}) for model {model}"
        )


def _count_tokens(
    text: Optional[str],
    model: str,
    counter: TokenCounter,
) -> int:
    """Count tokens in *text*, with repetitive-content defense.

    - Returns 0 for None or empty string.
    - If >50% of 4-grams are repeated, uses ``len(text) // 3`` as a
      fast estimate instead of calling the (potentially slow) counter.
    - Otherwise delegates to *counter(text, model)*.
    """
    if not text:
        return 0

    if _is_repetitive(text):
        return len(text) // 3

    return counter(text, model)


def _is_repetitive(text: str, *, ngram_size: int = 4, threshold: float = 0.9) -> bool:
    """Return True if more than *threshold* fraction of 4-grams are repeated."""
    if len(text) < ngram_size:
        return False

    total = len(text) - ngram_size + 1
    seen: set[str] = set()
    repeated = 0

    for i in range(total):
        gram = text[i : i + ngram_size]
        if gram in seen:
            repeated += 1
        else:
            seen.add(gram)

    return repeated / total > threshold


def get_model_budget(
    model: str,
    budget_ratio: float = 0.9,
    output_reserve: Optional[int] = None,
) -> int:
    """Compute the effective token budget for *model*.

    effective_budget = int(max_input * budget_ratio) - output_reserve

    If *output_reserve* is None, defaults to ``min(int(max_input * 0.1), 4096)``.
    """
    info = get_model_info(model)
    max_input = info["max_input_tokens"]

    if output_reserve is None:
        output_reserve = min(int(max_input * 0.1), 4096)

    return int(max_input * budget_ratio) - output_reserve


_DELIMITED_ENTRY_RE = re.compile(r"^===\s.*===\s*$")


def _truncate_context(
    context: str,
    max_tokens: int,
    model: str,
    counter: TokenCounter,
) -> tuple[str, int, int]:
    """Truncate P2 elastic content at entry boundaries.

    Splits *context* into logical entries delimited by ``=== ... ===`` lines.
    Iterates from newest (last) to oldest (first), accumulating token counts.
    Drops entire entries from the front when the budget is exceeded.

    If no delimiters are found the context is treated as a single atomic entry:
    it either fits entirely or is dropped entirely.

    Returns ``(truncated_context, tokens_used, entries_dropped)``.
    """
    if not context or not context.strip():
        return ("", 0, 0)

    # Detect whether context has delimited entries
    lines = context.split("\n")
    has_delimiters = any(_DELIMITED_ENTRY_RE.match(line) for line in lines)

    if not has_delimiters:
        # Atomic: single entry — fits or doesn't
        tokens = counter(context, model)
        if tokens <= max_tokens:
            return (context, tokens, 0)
        return ("", 0, 1)

    # Split into individual delimited entries (each non-blank line)
    entries = [line for line in lines if line.strip()]
    total_entries = len(entries)

    # Build from newest (end) to oldest (start), stopping when budget exceeded
    kept: list[str] = []
    for entry in reversed(entries):
        candidate = "\n".join([entry] + kept)
        candidate_tokens = counter(candidate, model)
        if candidate_tokens <= max_tokens:
            kept.insert(0, entry)
        else:
            break

    entries_dropped = total_entries - len(kept)
    if not kept:
        return ("", 0, total_entries)

    truncated = "\n".join(kept)
    tokens_used = counter(truncated, model)
    return (truncated, tokens_used, entries_dropped)
