"""Shared path ancestry helpers."""

from __future__ import annotations

from pathlib import Path


def is_path_within_base(resolved_base: Path, resolved_candidate: Path) -> bool:
    """Return whether an already-resolved candidate is the base or a descendant.

    Both arguments must already be fully resolved by the caller. This helper answers
    only the ancestry question and does not normalize inputs or shape errors.
    """
    try:
        resolved_candidate.relative_to(resolved_base)
    except ValueError:
        return False
    return True
