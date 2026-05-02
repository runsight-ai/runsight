"""Core soul assertion field removal governance.

Owner: packages/core block registration and schema test owners.
Boundary: core-owned tests must not keep stale soul-level assertion field
coverage after the field was removed from shared soul schema behavior.
Exit criteria: delete this suite once ordinary core schema and registration
tests make the retired soul field impossible to reintroduce without failing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_TARGET_FILES = {
    "core_auto_registration": REPO_ROOT
    / "packages"
    / "core"
    / "tests"
    / "test_auto_registration.py",
}

SOUL_FIELD_PATTERNS = (
    re.compile(r"\bassertions\s*=\s*\["),
    re.compile(r"\bassertions\s*=\s*None"),
    re.compile(r"\.assertions\b"),
    re.compile(r'\["assertions"\]'),
    re.compile(r"\['assertions'\]"),
    re.compile(r'"assertions"\s*:'),
    re.compile(r"'assertions'\s*:"),
)


def _count_soul_assertion_refs(filepath: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if any(pattern.search(stripped) for pattern in SOUL_FIELD_PATTERNS):
            hits.append((lineno, stripped))
    return hits


@pytest.mark.parametrize("target_name", sorted(CORE_TARGET_FILES))
def test_core_soul_tests_have_no_stale_soul_assertion_field_refs(target_name: str) -> None:
    filepath = CORE_TARGET_FILES[target_name]
    hits = _count_soul_assertion_refs(filepath)

    assert hits == [], (
        f"Expected zero stale soul field references in {filepath.name}, found {len(hits)}: {hits}"
    )


def test_total_stale_soul_assertion_refs_across_core_targets_is_zero() -> None:
    total_hits: list[tuple[str, int, str]] = []
    for label, filepath in CORE_TARGET_FILES.items():
        for lineno, line in _count_soul_assertion_refs(filepath):
            total_hits.append((label, lineno, line))

    assert total_hits == [], (
        "Expected zero stale soul field references across core targets, "
        f"found {len(total_hits)}:\n"
        + "\n".join(f"  {label}:{lineno}: {line}" for label, lineno, line in total_hits)
    )
