"""API soul assertion field removal governance.

Owner: apps/api soul domain and service test owners.
Boundary: API-owned soul tests must not keep stale soul-level assertion field
coverage after the field was removed from SoulEntity.
Exit criteria: delete this suite once ordinary API soul schema/service tests
make the retired soul field impossible to reintroduce without failing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]

API_TARGET_FILES = {
    "api_soul_schema_alignment": (
        REPO_ROOT / "apps" / "api" / "tests" / "domain" / "test_soul_schema_alignment.py"
    ),
    "api_soul_update_preservation": (
        REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_soul_update_preservation.py"
    ),
    "api_soul_service": (REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_soul_service.py"),
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


@pytest.mark.parametrize("target_name", sorted(API_TARGET_FILES))
def test_api_soul_tests_have_no_stale_soul_assertion_field_refs(target_name: str) -> None:
    filepath = API_TARGET_FILES[target_name]
    hits = _count_soul_assertion_refs(filepath)

    assert hits == [], (
        f"Expected zero stale soul field references in {filepath.name}, found {len(hits)}: {hits}"
    )


def test_total_stale_soul_assertion_refs_across_api_targets_is_zero() -> None:
    total_hits: list[tuple[str, int, str]] = []
    for label, filepath in API_TARGET_FILES.items():
        for lineno, line in _count_soul_assertion_refs(filepath):
            total_hits.append((label, lineno, line))

    assert total_hits == [], (
        "Expected zero stale soul field references across API targets, "
        f"found {len(total_hits)}:\n"
        + "\n".join(f"  {label}:{lineno}: {line}" for label, lineno, line in total_hits)
    )
