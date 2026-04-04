"""
Failing tests for RUN-190: Token windowing utility.

Tests cover:
- prune_messages removes oldest messages first (FIFO)
- 20-message / 50k-token history pruned to ~28.8k (90% of 32k)
- Newest messages preserved
- Empty list in → empty list out
- Single message exceeding budget → returned as-is
- Unknown model → fallback to 4096 token limit
- get_max_tokens helper resolves model → max_input_tokens * 0.9
- get_max_tokens falls back to 4096 for unknown models
"""

from unittest.mock import patch

from runsight_core.memory.windowing import get_max_tokens, prune_messages

# ===========================================================================
# Helpers
# ===========================================================================


def _make_messages(count: int) -> list[dict]:
    """Create *count* user/assistant message pairs (2 dicts each)."""
    messages: list[dict] = []
    for i in range(count):
        messages.append({"role": "user", "content": f"User message {i}"})
        messages.append({"role": "assistant", "content": f"Assistant message {i}"})
    return messages


# ===========================================================================
# 1. Core algorithm — prune_messages with explicit max_tokens
# ===========================================================================


class TestPruneMessagesNoPruningNeeded:
    """When total tokens <= max_tokens, messages are returned unchanged."""

    def test_small_history_no_pruning(self):
        """Messages well under budget come back untouched."""
        msgs = _make_messages(3)  # 6 messages total

        with patch("runsight_core.memory.windowing.token_counter", return_value=100):
            result = prune_messages(msgs, max_tokens=1000, model="gpt-4")

        assert result == msgs

    def test_exact_budget_no_pruning(self):
        """Messages exactly at budget are not pruned."""
        msgs = _make_messages(2)

        with patch("runsight_core.memory.windowing.token_counter", return_value=500):
            result = prune_messages(msgs, max_tokens=500, model="gpt-4")

        assert result == msgs


class TestPruneMessagesRemovesOldestFirst:
    """Oldest user/assistant pairs are removed first (FIFO)."""

    def test_oldest_pair_removed(self):
        """When over budget, the oldest pair is dropped first."""
        msgs = _make_messages(3)  # 6 messages: pairs 0, 1, 2

        # First call (full list): over budget. After removing pair 0: under budget.
        def fake_counter(model, messages):
            if len(messages) == 6:
                return 900
            if len(messages) == 4:
                return 400
            return 200

        with patch("runsight_core.memory.windowing.token_counter", side_effect=fake_counter):
            result = prune_messages(msgs, max_tokens=500, model="gpt-4")

        # Pair 0 removed, pairs 1 and 2 remain
        assert result == msgs[2:]

    def test_multiple_pairs_removed(self):
        """Multiple oldest pairs are removed until under budget."""
        msgs = _make_messages(4)  # 8 messages: pairs 0, 1, 2, 3

        def fake_counter(model, messages):
            # Simulate: full=1000, minus pair0=800, minus pair1=400
            counts = {8: 1000, 6: 800, 4: 400, 2: 200}
            return counts.get(len(messages), 100)

        with patch("runsight_core.memory.windowing.token_counter", side_effect=fake_counter):
            result = prune_messages(msgs, max_tokens=500, model="gpt-4")

        # Pairs 0 and 1 removed, pairs 2 and 3 remain
        assert result == msgs[4:]

    def test_newest_messages_always_preserved(self):
        """The most recent pair is never the one removed."""
        msgs = _make_messages(5)  # 10 messages

        def fake_counter(model, messages):
            # Always over budget until only last pair remains
            if len(messages) <= 2:
                return 100
            return 9999

        with patch("runsight_core.memory.windowing.token_counter", side_effect=fake_counter):
            result = prune_messages(msgs, max_tokens=500, model="gpt-4")

        # Only the newest pair survives
        assert result == msgs[-2:]


class TestPruneMessagesAcceptanceCriteria:
    """AC: 20-message history with 50k tokens, max 32k → pruned to ~28.8k."""

    def test_large_history_pruned_to_budget(self):
        """50k-token history pruned to fit within 32k max_tokens."""
        msgs = _make_messages(10)  # 20 messages (10 pairs)

        # Simulate: each pair ≈ 5000 tokens, total = 50000
        # After removing pairs until ≤ 32000:
        # 10 pairs = 50000, 9 = 45000, 8 = 40000, 7 = 35000, 6 = 30000 ✓
        def fake_counter(model, messages):
            num_pairs = len(messages) // 2
            return num_pairs * 5000

        with patch("runsight_core.memory.windowing.token_counter", side_effect=fake_counter):
            result = prune_messages(msgs, max_tokens=32000, model="gpt-4")

        # 6 pairs = 12 messages should remain (30000 ≤ 32000)
        assert len(result) == 12
        # The remaining messages are the 6 newest pairs
        assert result == msgs[-12:]


# ===========================================================================
# 2. Edge cases
# ===========================================================================


class TestPruneMessagesEdgeCases:
    """Edge cases: empty list, single message over budget."""

    def test_empty_list_returns_empty(self):
        """No messages → empty list, no crash."""
        result = prune_messages([], max_tokens=1000, model="gpt-4")
        assert result == []

    def test_single_message_exceeds_budget_returned_as_is(self):
        """A single message that exceeds the budget is returned as-is."""
        msgs = [{"role": "user", "content": "A very long message"}]

        with patch("runsight_core.memory.windowing.token_counter", return_value=99999):
            result = prune_messages(msgs, max_tokens=1000, model="gpt-4")

        assert result == msgs

    def test_single_pair_exceeds_budget_returned_as_is(self):
        """A single user/assistant pair that exceeds the budget is returned as-is."""
        msgs = [
            {"role": "user", "content": "Long question"},
            {"role": "assistant", "content": "Long answer"},
        ]

        with patch("runsight_core.memory.windowing.token_counter", return_value=99999):
            result = prune_messages(msgs, max_tokens=1000, model="gpt-4")

        assert result == msgs


# ===========================================================================
# 3. get_max_tokens — model info resolution with fallback
# ===========================================================================


class TestGetMaxTokens:
    """get_max_tokens resolves max_input_tokens from model name with 0.9 buffer."""

    def test_known_model_returns_90_percent(self):
        """Known model → max_input_tokens * 0.9."""
        with patch(
            "runsight_core.memory.windowing.get_model_info",
            return_value={"max_input_tokens": 128000},
        ):
            result = get_max_tokens("gpt-4")

        assert result == int(128000 * 0.9)

    def test_32k_model(self):
        """32k model → 32000 * 0.9 = 28800."""
        with patch(
            "runsight_core.memory.windowing.get_model_info",
            return_value={"max_input_tokens": 32000},
        ):
            result = get_max_tokens("gpt-4-32k")

        assert result == int(32000 * 0.9)

    def test_unknown_model_falls_back_to_4096(self):
        """Unknown model (get_model_info raises) → fallback to 4096."""
        with patch(
            "runsight_core.memory.windowing.get_model_info",
            side_effect=Exception("Unknown model"),
        ):
            result = get_max_tokens("totally-unknown-model")

        assert result == 4096

    def test_fallback_does_not_apply_buffer(self):
        """The 4096 fallback is the final value — no 0.9 multiplier on it."""
        with patch(
            "runsight_core.memory.windowing.get_model_info",
            side_effect=Exception("Unknown model"),
        ):
            result = get_max_tokens("fake-model")

        # 4096 is already conservative, no further reduction
        assert result == 4096


# ===========================================================================
# 4. Integration: prune_messages + get_max_tokens together
# ===========================================================================


class TestPruneWithModelResolution:
    """Verify prune_messages works with get_max_tokens-resolved budget."""

    def test_end_to_end_with_model_resolution(self):
        """Resolve max_tokens from model, then prune."""
        msgs = _make_messages(5)  # 10 messages

        def fake_counter(model, messages):
            return len(messages) * 500  # 500 tokens per message

        with patch(
            "runsight_core.memory.windowing.get_model_info",
            return_value={"max_input_tokens": 4000},
        ):
            max_tok = get_max_tokens("gpt-4")  # 4000 * 0.9 = 3600

        with patch("runsight_core.memory.windowing.token_counter", side_effect=fake_counter):
            result = prune_messages(msgs, max_tokens=max_tok, model="gpt-4")

        # 3600 / 500 = 7.2 → 6 messages fit (3 pairs)
        # 10 msgs = 5000, 8 = 4000, 6 = 3000 ✓
        assert len(result) == 6
        assert result == msgs[-6:]
