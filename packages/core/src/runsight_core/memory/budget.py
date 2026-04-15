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
    """Result of budget allocation: the instruction, context, messages, and diagnostic report."""

    instruction: str
    context: Optional[str]
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


_SAFETY_VALVE_OUTPUT_RESERVE = 256


def _count_messages_tokens(
    messages: list[dict],
    model: str,
    counter: TokenCounter,
) -> int:
    """Sum token counts across all message contents using the injected counter."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if content:
            total += counter(content, model)
    return total


def _prune_messages_with_counter(
    messages: list[dict],
    max_tokens: int,
    model: str,
    counter: TokenCounter,
) -> list[dict]:
    """Remove oldest message pairs (FIFO) until total tokens fit within *max_tokens*.

    Uses the injected *counter* instead of litellm's token_counter so callers
    can supply custom counting logic (e.g. len-based counters in tests).
    """
    if not messages:
        return []

    msgs = list(messages)

    while len(msgs) > 2:
        if _count_messages_tokens(msgs, model, counter) <= max_tokens:
            return msgs
        msgs = msgs[2:]

    # Last pair (or single message) — check if it fits
    if _count_messages_tokens(msgs, model, counter) <= max_tokens:
        return msgs
    return []


def _clean_orphaned_tool_messages(messages: list[dict]) -> list[dict]:
    """Remove orphaned tool-related messages after pruning.

    Orphan rules:
    - Remove ``role: "tool"`` messages whose ``tool_call_id`` has no matching
      ``tool_calls`` entry in any preceding assistant message.
    - Remove assistant messages with ``tool_calls`` that have no matching
      ``role: "tool"`` response after them.
    """
    # Collect all tool_call_ids from assistant messages
    assistant_call_ids: set[str] = set()
    for msg in messages:
        for tc in msg.get("tool_calls", []):
            assistant_call_ids.add(tc["id"])

    # Collect all tool response ids
    response_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            response_ids.add(msg["tool_call_id"])

    cleaned: list[dict] = []
    for msg in messages:
        # Remove orphaned tool responses (no matching assistant tool_call)
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            if msg["tool_call_id"] not in assistant_call_ids:
                continue

        # Remove orphaned assistant tool_calls (no matching tool response)
        if msg.get("tool_calls"):
            call_ids = {tc["id"] for tc in msg["tool_calls"]}
            if not call_ids.issubset(response_ids):
                continue

        cleaned.append(msg)

    return cleaned


def fit_to_budget(
    request: ContextBudgetRequest,
    counter: TokenCounter,
) -> BudgetedContext:
    """Allocate a context budget for *request* (Phase 1 + Phase 2).

    Phase 1: P1 accounting + safety valve.
    Phase 2: P3 pruning, orphan cleanup, P2 truncation, BudgetReport population.

    1. Count P1 tokens (system_prompt + instruction).
    2. Compute effective_budget via ``get_model_budget``.
    3. If P1 exceeds budget, apply safety valve (output_reserve=256) and retry.
    4. If still exceeded, raise ``ContextBudgetExceeded``.
    5. Prune P3 (conversation_history) via FIFO pair removal if over budget.
    6. Clean orphaned tool messages from pruned P3.
    7. Truncate P2 (context) if P1 + P3_pruned + P2 still exceeds budget.
    8. Return ``BudgetedContext`` with instruction, context, messages, and diagnostic report.
    """
    model = request.model

    # Count P1 tokens directly via the injected counter.
    sys_tokens = counter(request.system_prompt, model) if request.system_prompt else 0
    instr_tokens = counter(request.instruction, model) if request.instruction else 0
    p1_tokens = sys_tokens + instr_tokens

    # First attempt with original output_reserve
    effective_budget = get_model_budget(
        model,
        budget_ratio=request.budget_ratio,
        output_reserve=request.output_token_reserve,
    )

    # Safety valve: if P1 exceeds budget, retry with reduced output_reserve
    if p1_tokens > effective_budget:
        effective_budget = get_model_budget(
            model,
            budget_ratio=request.budget_ratio,
            output_reserve=_SAFETY_VALVE_OUTPUT_RESERVE,
        )
        if p1_tokens > effective_budget:
            raise ContextBudgetExceeded(
                p1_tokens=p1_tokens,
                effective_budget=effective_budget,
                model=model,
            )

    remaining = effective_budget - p1_tokens

    # --- Phase 2: Count P2 and P3 tokens before any adjustments ---
    p2_tokens_before = _count_tokens(request.context, model, counter)
    p3_tokens_before = _count_messages_tokens(request.conversation_history, model, counter)

    # --- Phase 2 step 1: Prune P3 (lowest priority, pruned first) ---
    # P3 budget = remaining minus what P2 needs (P2 has higher priority)
    p3_budget = max(0, remaining - p2_tokens_before)
    messages = list(request.conversation_history)
    if p3_tokens_before > p3_budget:
        messages = _prune_messages_with_counter(messages, p3_budget, model, counter)

    # Clean orphaned tool messages
    messages = _clean_orphaned_tool_messages(messages)

    p3_tokens_after = _count_messages_tokens(messages, model, counter)

    # Count pairs dropped
    original_pair_count = len(request.conversation_history) // 2
    remaining_pair_count = len(messages) // 2
    p3_pairs_dropped = original_pair_count - remaining_pair_count

    # --- Phase 2 step 2: Truncate P2 if still over budget ---
    remaining_for_p2 = max(0, remaining - p3_tokens_after)
    context = request.context

    if p2_tokens_before > remaining_for_p2:
        context, p2_tokens_after, _ = _truncate_context(context, remaining_for_p2, model, counter)
    else:
        p2_tokens_after = p2_tokens_before

    total_tokens = p1_tokens + p2_tokens_after + p3_tokens_after

    output_reserve = request.output_token_reserve if request.output_token_reserve is not None else 0

    report = BudgetReport(
        model=model,
        max_input_tokens=0,
        output_reserve=output_reserve,
        effective_budget=effective_budget,
        p1_tokens=p1_tokens,
        p2_tokens_before=p2_tokens_before,
        p2_tokens_after=p2_tokens_after,
        p3_tokens_before=p3_tokens_before,
        p3_tokens_after=p3_tokens_after,
        p3_pairs_dropped=p3_pairs_dropped,
        total_tokens=total_tokens,
        headroom=effective_budget - total_tokens,
        warnings=[],
    )

    return BudgetedContext(
        instruction=request.instruction,
        context=context,
        messages=messages,
        report=report,
    )


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
