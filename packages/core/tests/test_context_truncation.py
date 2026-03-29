"""
Failing tests for RUN-258: P2 context truncation utility.

Tests cover:
- _truncate_context is importable from budget module
- Empty context returns ("", 0, 0)
- Context that fits within budget is returned unchanged
- Context with === ... === delimiters that exceeds budget drops oldest entries
- Context with no delimiters that exceeds budget: atomic (entire or empty)
- Context with no delimiters that fits: returned unchanged
- Multiple entries, some dropped: correct count of dropped entries
- Token count accuracy with a mock counter that returns len(text)
"""


# ===========================================================================
# Helpers
# ===========================================================================


def _len_counter(text: str, model: str) -> int:
    """Mock TokenCounter that returns len(text) as the token count."""
    return len(text)


def _make_delimited_entries(entries: list[str]) -> str:
    """Build a context string with === ... === delimiters around each entry."""
    parts = []
    for entry in entries:
        parts.append(f"=== {entry} ===")
    return "\n".join(parts)


# ===========================================================================
# 1. Importability
# ===========================================================================


class TestTruncateContextImportable:
    """_truncate_context is importable from budget module."""

    def test_truncate_context_importable(self):
        """_truncate_context should be importable from runsight_core.memory.budget."""
        from runsight_core.memory.budget import _truncate_context  # noqa: F401


# ===========================================================================
# 2. Empty context
# ===========================================================================


class TestTruncateContextEmpty:
    """Empty context returns ('', 0, 0)."""

    def test_empty_string_returns_empty_tuple(self):
        """Empty string context returns ('', 0, 0)."""
        from runsight_core.memory.budget import _truncate_context

        result = _truncate_context("", max_tokens=100, model="gpt-4", counter=_len_counter)
        assert result == ("", 0, 0)

    def test_whitespace_only_treated_as_empty(self):
        """Whitespace-only context is treated like empty."""
        from runsight_core.memory.budget import _truncate_context

        result = _truncate_context("   ", max_tokens=100, model="gpt-4", counter=_len_counter)
        # Whitespace-only should either be treated as empty or as atomic content
        # that fits. Either way, tokens_used and entries_dropped should make sense.
        truncated, tokens_used, entries_dropped = result
        assert entries_dropped == 0


# ===========================================================================
# 3. Context fits within budget — returned unchanged
# ===========================================================================


class TestTruncateContextFitsWithinBudget:
    """Context that fits within budget is returned unchanged."""

    def test_short_context_returned_unchanged(self):
        """Short plain context within budget comes back as-is."""
        from runsight_core.memory.budget import _truncate_context

        context = "Hello world"
        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=1000,
            model="gpt-4",
            counter=_len_counter,
        )
        assert truncated == context
        assert tokens_used == len(context)
        assert entries_dropped == 0

    def test_delimited_context_within_budget_returned_unchanged(self):
        """Delimited context that fits within budget comes back intact."""
        from runsight_core.memory.budget import _truncate_context

        entries = ["entry one", "entry two", "entry three"]
        context = _make_delimited_entries(entries)
        # Budget is large enough to fit everything
        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=10000,
            model="gpt-4",
            counter=_len_counter,
        )
        assert truncated == context
        assert entries_dropped == 0
        assert tokens_used == len(context)


# ===========================================================================
# 4. Delimited context exceeding budget — oldest entries dropped
# ===========================================================================


class TestTruncateContextDelimitedExceedsBudget:
    """Context with === ... === delimiters that exceeds budget drops oldest entries."""

    def test_drops_oldest_entries_first(self):
        """When budget exceeded, oldest (first) entries are dropped."""
        from runsight_core.memory.budget import _truncate_context

        entries = ["old entry", "middle entry", "newest entry"]
        context = _make_delimited_entries(entries)

        # Set budget to only fit the newest entry plus delimiter
        newest_line = "=== newest entry ==="
        budget = len(newest_line) + 1  # tight budget: fits only newest

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=budget,
            model="gpt-4",
            counter=_len_counter,
        )
        # Oldest entries should be dropped
        assert "old entry" not in truncated
        assert "middle entry" not in truncated
        assert "newest entry" in truncated
        assert entries_dropped == 2

    def test_drops_minimum_entries_needed(self):
        """Only drops enough oldest entries to fit within budget."""
        from runsight_core.memory.budget import _truncate_context

        # Create 5 entries of roughly equal size
        entries = [f"entry number {i:03d}" for i in range(5)]
        context = _make_delimited_entries(entries)

        # Each delimited line: "=== entry number XXX ===" = ~24 chars
        # Budget to fit 3 entries: 3 lines + 2 newlines
        single_line = "=== entry number 000 ==="
        three_lines_budget = len(single_line) * 3 + 2 * len("\n") + 5  # small buffer

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=three_lines_budget,
            model="gpt-4",
            counter=_len_counter,
        )

        assert entries_dropped == 2  # dropped entries 0 and 1
        assert "entry number 000" not in truncated
        assert "entry number 001" not in truncated
        # Newest 3 should remain
        assert "entry number 002" in truncated
        assert "entry number 003" in truncated
        assert "entry number 004" in truncated

    def test_preserves_newest_entry_when_all_others_exceed(self):
        """Even when heavily over budget, at least the newest entry is kept."""
        from runsight_core.memory.budget import _truncate_context

        entries = ["A" * 100, "B" * 100, "C" * 50]
        context = _make_delimited_entries(entries)

        # Budget only fits the last entry
        budget = len("=== " + "C" * 50 + " ===") + 1

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=budget,
            model="gpt-4",
            counter=_len_counter,
        )

        assert "C" * 50 in truncated
        assert entries_dropped == 2


# ===========================================================================
# 5. No delimiters — atomic behavior
# ===========================================================================


class TestTruncateContextNoDelimitersAtomic:
    """Context with no delimiters is atomic: returned whole if fits, or empty."""

    def test_no_delimiters_fits_returned_unchanged(self):
        """Plain text within budget is returned unchanged."""
        from runsight_core.memory.budget import _truncate_context

        context = "Just some plain text without any delimiters"
        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=1000,
            model="gpt-4",
            counter=_len_counter,
        )
        assert truncated == context
        assert tokens_used == len(context)
        assert entries_dropped == 0

    def test_no_delimiters_exceeds_budget_returns_empty(self):
        """Plain text exceeding budget is dropped entirely (atomic)."""
        from runsight_core.memory.budget import _truncate_context

        context = "A" * 500
        # Budget smaller than context
        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=100,
            model="gpt-4",
            counter=_len_counter,
        )
        assert truncated == ""
        assert tokens_used == 0
        assert entries_dropped == 1  # The single atomic entry was dropped


# ===========================================================================
# 6. Multiple entries, some dropped — correct drop count
# ===========================================================================


class TestTruncateContextDropCount:
    """Returns accurate count of dropped entries."""

    def test_drop_count_matches_entries_removed(self):
        """entries_dropped accurately reflects how many entries were removed."""
        from runsight_core.memory.budget import _truncate_context

        entries = [f"entry {i}" for i in range(10)]
        context = _make_delimited_entries(entries)

        # Budget to fit about 4 entries
        single_line = "=== entry 0 ==="
        four_lines_budget = len(single_line) * 4 + 3 * len("\n") + 20

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=four_lines_budget,
            model="gpt-4",
            counter=_len_counter,
        )

        # Count how many entries actually remain
        remaining = sum(1 for i in range(10) if f"entry {i}" in truncated)
        assert entries_dropped == 10 - remaining
        assert entries_dropped > 0  # Some must have been dropped

    def test_zero_drops_when_all_fit(self):
        """When everything fits, entries_dropped is 0."""
        from runsight_core.memory.budget import _truncate_context

        entries = ["a", "b", "c"]
        context = _make_delimited_entries(entries)

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=99999,
            model="gpt-4",
            counter=_len_counter,
        )
        assert entries_dropped == 0


# ===========================================================================
# 7. Token count accuracy
# ===========================================================================


class TestTruncateContextTokenCountAccuracy:
    """Returned tokens_used matches what the counter reports for the result."""

    def test_tokens_used_matches_counter_on_truncated_output(self):
        """tokens_used equals counter(truncated_context, model)."""
        from runsight_core.memory.budget import _truncate_context

        entries = [f"{'X' * 50}" for _ in range(5)]
        context = _make_delimited_entries(entries)

        # Budget fits ~2 entries
        budget = len("=== " + "X" * 50 + " ===") * 2 + len("\n") + 5

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=budget,
            model="gpt-4",
            counter=_len_counter,
        )

        # tokens_used should equal what the counter returns for the truncated result
        assert tokens_used == _len_counter(truncated, "gpt-4")

    def test_tokens_used_zero_for_empty_result(self):
        """When context is empty, tokens_used is 0."""
        from runsight_core.memory.budget import _truncate_context

        truncated, tokens_used, entries_dropped = _truncate_context(
            "",
            max_tokens=100,
            model="gpt-4",
            counter=_len_counter,
        )
        assert tokens_used == 0

    def test_never_exceeds_budget(self):
        """tokens_used should never exceed max_tokens."""
        from runsight_core.memory.budget import _truncate_context

        entries = [f"entry {i} with some padding text here" for i in range(20)]
        context = _make_delimited_entries(entries)
        budget = 200

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=budget,
            model="gpt-4",
            counter=_len_counter,
        )

        assert tokens_used <= budget

    def test_whole_entries_not_partial(self):
        """Truncated output only contains whole delimited entries, never partial."""
        from runsight_core.memory.budget import _truncate_context

        entries = ["alpha content here", "beta content here", "gamma content here"]
        context = _make_delimited_entries(entries)
        # Budget that can fit ~2 entries
        budget = len("=== alpha content here ===") * 2 + len("\n") + 5

        truncated, tokens_used, entries_dropped = _truncate_context(
            context,
            max_tokens=budget,
            model="gpt-4",
            counter=_len_counter,
        )

        # Each remaining entry should be fully intact with delimiters
        for line in truncated.strip().split("\n"):
            if line.strip():
                assert line.strip().startswith("===") and line.strip().endswith("==="), (
                    f"Partial entry found: {line!r}"
                )
