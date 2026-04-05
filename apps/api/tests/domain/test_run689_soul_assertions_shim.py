"""
RUN-689 — Failing tests for SoulEntity.assertions compat shim removal.

SoulEntity uses ``extra="allow"`` which preserves any unknown YAML fields
generically.  The explicit ``assertions`` field is a backward-compat shim
that must be deleted.  These tests verify the shim is gone.
"""

from __future__ import annotations

from runsight_api.domain.value_objects import SoulEntity


class TestSoulEntityAssertionsShimRemoved:
    """The explicit 'assertions' field must not exist on SoulEntity."""

    def test_assertions_not_in_explicit_model_fields(self) -> None:
        """SoulEntity.model_fields must not contain 'assertions'.

        The field was a backward-compat shim.  With extra='allow', any
        unknown key (including 'assertions') is still preserved at runtime
        without needing a declared field.
        """
        assert "assertions" not in SoulEntity.model_fields, (
            "SoulEntity still declares an explicit 'assertions' field — "
            "remove the compat shim; extra='allow' handles it generically"
        )

    def test_assertions_data_still_preserved_via_extra_allow(self) -> None:
        """Even without an explicit field, passing assertions data should
        be preserved by the extra='allow' config."""
        soul = SoulEntity(
            id="s1",
            role="Tester",
            assertions=[{"type": "contains", "value": "hello"}],
        )
        # The data must survive — extra="allow" keeps it
        assert soul.assertions == [{"type": "contains", "value": "hello"}]
