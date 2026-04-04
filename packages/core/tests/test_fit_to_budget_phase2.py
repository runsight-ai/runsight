"""
Failing tests for RUN-260: fit_to_budget() Phase 2 — P2 truncation, P3 pruning, orphan cleanup.

Tests cover:
- P3 history is pruned when total exceeds budget (pairs removed from front)
- P2 context is truncated only after P3 is fully pruned
- BudgetReport has correct p2_tokens_before/after and p3_tokens_before/after
- Orphaned tool messages are removed (tool_call with no response, tool response with no call)
- Empty P2 (no context) works — only P3 pruned
- Empty P3 (no history) works — only P2 truncated
- Both empty (pure P1 call) works
- p3_pairs_dropped count is accurate
"""

from unittest.mock import patch

from runsight_core.memory.budget import (
    BudgetedContext,
    ContextBudgetRequest,
    fit_to_budget,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _len_counter(text: str, model: str) -> int:
    """Mock TokenCounter: 1 token per character."""
    return len(text)


def _make_request(**overrides) -> ContextBudgetRequest:
    """Build a ContextBudgetRequest with sensible defaults, overrideable."""
    defaults = dict(
        model="test-model",
        system_prompt="sys",  # 3 tokens
        instruction="instr",  # 5 tokens → P1 = 8 tokens
        context="",
        conversation_history=[],
        budget_ratio=0.9,
        output_token_reserve=None,
    )
    defaults.update(overrides)
    return ContextBudgetRequest(**defaults)


def _make_history_pairs(count: int, content_size: int = 10) -> list[dict]:
    """Create *count* user/assistant message pairs with predictable content sizes."""
    messages: list[dict] = []
    for i in range(count):
        messages.append({"role": "user", "content": "u" * content_size})
        messages.append({"role": "assistant", "content": "a" * content_size})
    return messages


def _sum_message_tokens(messages: list[dict]) -> int:
    """Sum len(content) across all messages (matching _len_counter logic)."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if content:
            total += len(content)
    return total


# ===========================================================================
# 1. P3 history is pruned when total exceeds budget
# ===========================================================================


class TestP3PrunedWhenOverBudget:
    """P3 conversation history is pruned (FIFO pairs from front) when total exceeds budget."""

    def test_p3_pairs_removed_from_front(self):
        """Oldest pairs are removed first when P3 pushes total over budget."""
        # P1 = 8 tokens (sys=3 + instr=5)
        # P3 = 5 pairs, each pair = 20 tokens (10+10) → P3 total = 100 tokens
        # Budget = 60 → remaining after P1 = 52 → must prune P3 down to ≤52
        # That means we can keep at most 2 pairs (40 tokens) — 3 pairs dropped
        history = _make_history_pairs(5, content_size=10)

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=60):
            result = fit_to_budget(request, _len_counter)

        # The oldest pairs should have been removed; only newest pairs remain
        # The result messages should be a strict suffix of the original history
        assert len(result.messages) < len(history)
        # Newest messages are preserved (last entries from history)
        assert result.messages == history[-(len(result.messages)) :]

    def test_p3_not_pruned_when_under_budget(self):
        """When total fits within budget, P3 history is untouched."""
        history = _make_history_pairs(3, content_size=5)  # 3 pairs = 30 tokens

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        assert result.messages == history


# ===========================================================================
# 2. P2 context truncated only after P3 is fully pruned
# ===========================================================================


class TestP2TruncatedAfterP3FullyPruned:
    """P2 context is truncated only when P3 is fully exhausted and still over budget."""

    def test_p3_pruned_first_p2_untouched_if_fits(self):
        """When pruning P3 alone brings total under budget, P2 is not truncated."""
        # P1 = 8 tokens
        # P2 = delimited context with 3 entries, ~57 tokens
        context = "=== entry one ===\n=== entry two ===\n=== entry three ==="
        # P3 = 5 pairs × 20 tokens = 100 tokens
        history = _make_history_pairs(5, content_size=10)

        # Budget = 80 → after P1 (8), remaining = 72
        # P2 ≈ 57 chars → remaining for P3 after P2 = ~15 → heavily prune P3
        request = _make_request(
            context=context,
            conversation_history=history,
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=80):
            result = fit_to_budget(request, _len_counter)

        # P2 context should be preserved in full (not truncated)
        assert result.task.context == context
        # P3 must have been pruned (total P1+P2+P3 = 8+57+100 = 165 > 80)
        assert len(result.messages) < len(history)

    def test_p2_truncated_when_p3_fully_pruned_still_over(self):
        """When P3 is fully pruned but total still exceeds budget, P2 is truncated."""
        # P1 = 8 tokens
        # P2 = large context that needs truncation
        context = "=== old entry ===\n=== mid entry ===\n=== new entry ==="
        # P3 = 1 pair = 20 tokens (will be fully pruned)
        history = _make_history_pairs(1, content_size=10)

        # Budget = 30 → after P1 (8), remaining = 22
        # Even with P3 fully pruned (0), P2 (~55 chars) > 22 → must truncate P2
        request = _make_request(
            context=context,
            conversation_history=history,
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        # P2 should be truncated — shorter than original
        assert len(result.task.context) < len(context)
        # P3 should be fully pruned
        assert len(result.messages) == 0 or _sum_message_tokens(result.messages) == 0


# ===========================================================================
# 3. BudgetReport has correct before/after token counts
# ===========================================================================


class TestBudgetReportTokenCounts:
    """BudgetReport includes accurate p2/p3 before/after token counts."""

    def test_p3_tokens_before_reflects_original_history(self):
        """p3_tokens_before equals the total tokens in the original conversation_history."""
        history = _make_history_pairs(4, content_size=10)  # 4 pairs = 80 tokens
        expected_p3_before = _sum_message_tokens(history)

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p3_tokens_before == expected_p3_before

    def test_p3_tokens_after_reflects_pruned_history(self):
        """p3_tokens_after equals the total tokens in the pruned conversation_history."""
        history = _make_history_pairs(4, content_size=10)  # 80 tokens total

        request = _make_request(
            conversation_history=history,
            context="",
        )

        # Budget tight enough to force pruning
        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        # p3_tokens_after should match what's in the result messages
        actual_p3_after = _sum_message_tokens(result.messages)
        assert result.report.p3_tokens_after == actual_p3_after

    def test_p3_tokens_after_less_than_before_when_pruned(self):
        """When P3 is pruned, p3_tokens_after < p3_tokens_before."""
        history = _make_history_pairs(5, content_size=10)  # 100 tokens

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p3_tokens_after < result.report.p3_tokens_before

    def test_p2_tokens_before_reflects_original_context(self):
        """p2_tokens_before equals the token count of the original context."""
        context = "=== old entry ===\n=== mid entry ===\n=== new entry ==="
        expected_p2_before = len(context)

        request = _make_request(
            context=context,
            conversation_history=[],
        )

        # Budget tight enough to force P2 truncation
        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p2_tokens_before == expected_p2_before

    def test_p2_tokens_after_reflects_truncated_context(self):
        """p2_tokens_after equals the token count of the truncated context."""
        context = "=== old entry ===\n=== mid entry ===\n=== new entry ==="

        request = _make_request(
            context=context,
            conversation_history=[],
        )

        # Budget so tight P2 must be truncated: P1=8, remaining=22, P2=53
        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        # p2_tokens_after should match the actual truncated context length
        actual_p2_after = len(result.task.context) if result.task.context else 0
        assert result.report.p2_tokens_after == actual_p2_after
        # And it must be less than before (truncation happened)
        assert result.report.p2_tokens_after < result.report.p2_tokens_before

    def test_p2_tokens_after_less_than_before_when_truncated(self):
        """When P2 is truncated, p2_tokens_after < p2_tokens_before."""
        context = "=== old entry ===\n=== mid entry ===\n=== new entry ==="

        request = _make_request(
            context=context,
            conversation_history=[],
        )

        # Budget so tight that P2 must be truncated
        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p2_tokens_after < result.report.p2_tokens_before


# ===========================================================================
# 4. Orphaned tool messages are removed
# ===========================================================================


class TestOrphanedToolMessageCleanup:
    """After P3 pruning, orphaned tool messages are removed."""

    def test_orphaned_tool_response_removed(self):
        """A tool response whose matching assistant tool_call was pruned is removed."""
        # History: pair0 (pruned), pair1 has tool_call, pair2 is tool response
        # If pair1's assistant (with tool_calls) is pruned, pair2's tool response is orphaned
        history = [
            # Pair 0 — will be pruned (oldest)
            {"role": "user", "content": "u" * 20},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_old", "function": {"name": "fn", "arguments": "{}"}}],
            },
            # Tool response for call_old — should become orphaned after pruning
            {"role": "tool", "content": "result_old", "tool_call_id": "call_old"},
            # Pair 1 — should survive
            {"role": "user", "content": "u" * 5},
            {"role": "assistant", "content": "a" * 5},
        ]

        request = _make_request(
            conversation_history=history,
            context="",
        )

        # Budget allows P1 (8) + last pair (10) but not the old tool exchange
        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        # The orphaned tool response for "call_old" should not appear
        tool_ids = [m.get("tool_call_id") for m in result.messages if m.get("role") == "tool"]
        assert "call_old" not in tool_ids

    def test_orphaned_assistant_tool_calls_removed(self):
        """An assistant message with tool_calls whose tool responses were pruned is removed."""
        history = [
            # Pair 0 — regular pair, will survive
            {"role": "user", "content": "u" * 5},
            {"role": "assistant", "content": "a" * 5},
            # Pair 1 — assistant with tool_call; but the tool response comes later
            {"role": "user", "content": "u" * 5},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_abc", "function": {"name": "fn", "arguments": "{}"}}],
            },
            # Tool response was at the end and got pruned somehow, or consider:
            # We simulate: assistant with tool_calls but no matching tool response in result
        ]
        # In this scenario the assistant message at index 3 has tool_calls with id "call_abc"
        # but there's no tool response message with tool_call_id "call_abc" in the result.
        # The orphan cleanup should remove this assistant message.

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        # The assistant message with tool_calls whose responses are missing should be removed
        for msg in result.messages:
            if msg.get("tool_calls"):
                tool_call_ids = {tc["id"] for tc in msg["tool_calls"]}
                # Every tool_call must have a matching tool response
                response_ids = {
                    m.get("tool_call_id") for m in result.messages if m.get("role") == "tool"
                }
                assert tool_call_ids.issubset(response_ids), (
                    f"Assistant tool_calls {tool_call_ids} have no matching responses"
                )

    def test_valid_tool_pairs_preserved(self):
        """Complete tool call + response pairs that survived pruning are kept intact."""
        history = [
            {"role": "user", "content": "u" * 5},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_ok", "function": {"name": "fn", "arguments": "{}"}}],
            },
            {"role": "tool", "content": "result", "tool_call_id": "call_ok"},
            {"role": "assistant", "content": "final answer"},
        ]

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        # Both the tool_call assistant message and tool response should be present
        tool_call_ids = set()
        for msg in result.messages:
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_call_ids.add(tc["id"])

        response_ids = {m.get("tool_call_id") for m in result.messages if m.get("role") == "tool"}
        assert "call_ok" in tool_call_ids
        assert "call_ok" in response_ids


# ===========================================================================
# 5. Empty P2 (no context) — only P3 pruned
# ===========================================================================


class TestEmptyP2OnlyP3Pruned:
    """When P2 is empty, only P3 is pruned to fit budget."""

    def test_empty_context_p3_pruned_to_fit(self):
        """With no context, P3 alone is pruned to meet budget."""
        history = _make_history_pairs(5, content_size=10)  # 100 tokens

        request = _make_request(
            context="",
            conversation_history=history,
        )

        # Budget = 50 → after P1 (8), remaining = 42 → P3 must fit in 42
        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        # P3 should be pruned
        assert len(result.messages) < len(history)
        # P2 stays empty
        assert result.task.context == ""
        # Report reflects empty P2
        assert result.report.p2_tokens_before == 0
        assert result.report.p2_tokens_after == 0

    def test_empty_context_report_has_correct_p3_before(self):
        """With empty P2, p3_tokens_before still reflects the original P3."""
        history = _make_history_pairs(3, content_size=10)
        expected_p3_before = _sum_message_tokens(history)

        request = _make_request(
            context="",
            conversation_history=history,
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p3_tokens_before == expected_p3_before


# ===========================================================================
# 6. Empty P3 (no history) — only P2 truncated
# ===========================================================================


class TestEmptyP3OnlyP2Truncated:
    """When P3 is empty, only P2 context is truncated to fit budget."""

    def test_empty_history_p2_truncated_to_fit(self):
        """With no history, P2 alone is truncated to meet budget."""
        context = "=== old entry ===\n=== mid entry ===\n=== new entry ==="

        request = _make_request(
            context=context,
            conversation_history=[],
        )

        # Budget = 30 → after P1 (8), remaining = 22 → P2 must fit in 22
        with patch("runsight_core.memory.budget.get_model_budget", return_value=30):
            result = fit_to_budget(request, _len_counter)

        # P2 should be truncated
        assert len(result.task.context) < len(context)
        # P3 stays empty
        assert result.messages == []
        # Report reflects empty P3
        assert result.report.p3_tokens_before == 0
        assert result.report.p3_tokens_after == 0
        assert result.report.p3_pairs_dropped == 0

    def test_empty_history_report_has_correct_p2_before(self):
        """With empty P3, p2_tokens_before still reflects the original P2."""
        context = "=== old ===\n=== new ==="
        expected_p2_before = len(context)

        request = _make_request(
            context=context,
            conversation_history=[],
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=20):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p2_tokens_before == expected_p2_before


# ===========================================================================
# 7. Both P2 and P3 empty (pure P1 call)
# ===========================================================================


class TestBothEmpty:
    """When both P2 and P3 are empty, fit_to_budget handles it gracefully."""

    def test_pure_p1_call_succeeds(self):
        """No context, no history — just P1. Should work without error."""
        request = _make_request(
            context="",
            conversation_history=[],
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        assert isinstance(result, BudgetedContext)
        assert result.messages == []
        assert result.task.context == ""

    def test_pure_p1_report_zeroed(self):
        """Report shows zero for all P2/P3 fields when both are empty."""
        request = _make_request(
            context="",
            conversation_history=[],
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p2_tokens_before == 0
        assert result.report.p2_tokens_after == 0
        assert result.report.p3_tokens_before == 0
        assert result.report.p3_tokens_after == 0
        assert result.report.p3_pairs_dropped == 0


# ===========================================================================
# 8. p3_pairs_dropped count is accurate
# ===========================================================================


class TestP3PairsDroppedCount:
    """p3_pairs_dropped accurately reflects the number of message pairs removed."""

    def test_pairs_dropped_count_matches_actual_pruning(self):
        """p3_pairs_dropped equals (original_pairs - remaining_pairs)."""
        history = _make_history_pairs(5, content_size=10)  # 5 pairs, 100 tokens
        original_pair_count = 5

        request = _make_request(
            conversation_history=history,
            context="",
        )

        # Budget = 50 → after P1 (8), remaining = 42 → 2 pairs (40 tokens) fit
        # So 3 pairs should be dropped
        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        remaining_pair_count = len(result.messages) // 2
        expected_dropped = original_pair_count - remaining_pair_count
        assert result.report.p3_pairs_dropped == expected_dropped
        # Must have actually dropped some pairs
        assert result.report.p3_pairs_dropped > 0

    def test_pairs_dropped_zero_when_no_pruning(self):
        """When P3 is not pruned, p3_pairs_dropped is 0."""
        history = _make_history_pairs(2, content_size=5)  # 2 pairs, 20 tokens

        request = _make_request(
            conversation_history=history,
            context="",
        )

        with patch("runsight_core.memory.budget.get_model_budget", return_value=1000):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p3_pairs_dropped == 0

    def test_all_pairs_dropped_when_budget_allows_none(self):
        """When budget is so tight that no P3 pairs fit, all are dropped."""
        history = _make_history_pairs(3, content_size=10)  # 3 pairs, 60 tokens

        request = _make_request(
            conversation_history=history,
            context="",
        )

        # Budget = 9 → after P1 (8), remaining = 1 → no pair fits (each pair = 20)
        with patch("runsight_core.memory.budget.get_model_budget", return_value=9):
            result = fit_to_budget(request, _len_counter)

        assert result.report.p3_pairs_dropped == 3
        assert result.messages == []


# ===========================================================================
# 9. Total tokens and headroom updated after Phase 2
# ===========================================================================


class TestTotalTokensAndHeadroomAfterPhase2:
    """total_tokens and headroom reflect the state after P2/P3adjustments."""

    def test_total_tokens_reflects_final_state(self):
        """total_tokens = p1_tokens + p2_tokens_after + p3_tokens_after."""
        history = _make_history_pairs(5, content_size=10)  # 100 tokens
        context = "=== entry ===\n=== another ==="  # ~29 tokens

        request = _make_request(
            context=context,
            conversation_history=history,
        )

        # Budget forces pruning so P3 is partially kept
        with patch("runsight_core.memory.budget.get_model_budget", return_value=60):
            result = fit_to_budget(request, _len_counter)

        expected_total = (
            result.report.p1_tokens + result.report.p2_tokens_after + result.report.p3_tokens_after
        )
        assert result.report.total_tokens == expected_total
        # P3 tokens should be included in total (not zero)
        assert result.report.p3_tokens_after > 0 or len(result.messages) == 0

    def test_headroom_reflects_final_budget_minus_total(self):
        """headroom = effective_budget - total_tokens (after Phase 2 adjustments)."""
        history = _make_history_pairs(3, content_size=10)  # 60 tokens

        request = _make_request(
            context="",
            conversation_history=history,
        )

        # Budget forces pruning: P1=8, P3=60, total=68 > 50
        with patch("runsight_core.memory.budget.get_model_budget", return_value=50):
            result = fit_to_budget(request, _len_counter)

        assert result.report.headroom == result.report.effective_budget - result.report.total_tokens
        assert result.report.headroom >= 0
        # total_tokens must include P3 (not just P1+P2)
        assert result.report.total_tokens > result.report.p1_tokens
