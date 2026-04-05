"""
Failing tests for RUN-690: Delete duplicate ``_resolve_soul()`` from parser.py.

``_resolve_soul`` in ``parser.py`` is an exact duplicate of ``resolve_soul``
in ``blocks/_helpers.py``.  The helpers version is the live one — imported by
dispatch, linear, synthesize, and gate block builders.  The parser copy has
zero call sites and must be removed.

AC1: parser.py must not contain ``def _resolve_soul``
AC2: block builders still work via the ``_helpers.py`` version
"""

from __future__ import annotations

import inspect

import pytest

# ===========================================================================
# AC1: _resolve_soul must not exist in parser.py
# ===========================================================================


class TestResolvedSoulRemovedFromParser:
    """The dead ``_resolve_soul`` function must be deleted from parser.py."""

    def test_parser_module_has_no_resolve_soul_attribute(self):
        """``hasattr(parser, '_resolve_soul')`` must be False."""
        from runsight_core.yaml import parser

        assert not hasattr(parser, "_resolve_soul"), (
            "_resolve_soul still exists as an attribute on the parser module — "
            "the duplicate must be deleted"
        )

    def test_parser_source_has_no_resolve_soul_definition(self):
        """The source text of parser.py must not contain ``def _resolve_soul``."""
        from runsight_core.yaml import parser

        source = inspect.getsource(parser)
        assert "def _resolve_soul(" not in source, (
            "parser.py source still contains 'def _resolve_soul(' — "
            "the dead function definition must be removed"
        )


# ===========================================================================
# AC2: The live resolve_soul in _helpers.py still works correctly
# ===========================================================================


class TestHelperResolveSoulStillFunctions:
    """``resolve_soul`` in ``blocks/_helpers.py`` must remain functional."""

    def test_resolve_soul_returns_matching_soul(self):
        """resolve_soul returns the Soul when ref exists in souls_map."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        soul = Soul(id="s1", role="Tester", system_prompt="Test prompt")
        result = resolve_soul("s1", {"s1": soul})
        assert result is soul

    def test_resolve_soul_raises_for_missing_ref(self):
        """resolve_soul raises ValueError when ref is not in souls_map."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        souls_map = {
            "exists": Soul(id="e1", role="R", system_prompt="P"),
        }
        with pytest.raises(ValueError, match="missing_ref"):
            resolve_soul("missing_ref", souls_map)

    def test_resolve_soul_error_lists_available_souls(self):
        """The error message from resolve_soul lists available soul keys."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        souls_map = {
            "alpha": Soul(id="a", role="R", system_prompt="P"),
            "beta": Soul(id="b", role="R", system_prompt="P"),
        }
        with pytest.raises(ValueError, match="alpha") as exc_info:
            resolve_soul("nope", souls_map)
        # Both available souls must appear in the error message
        assert "beta" in str(exc_info.value)

    def test_resolve_soul_is_importable_from_helpers(self):
        """Block builders import resolve_soul from _helpers, not parser."""
        from runsight_core.blocks._helpers import resolve_soul

        assert callable(resolve_soul)
