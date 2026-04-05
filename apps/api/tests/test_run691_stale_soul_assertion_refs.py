"""RUN-691: Verify stale soul-assertion references are removed from test files.

Four test files use `assertions` as a soul field to test unknown-field preservation.
The `assertions` field is being retired from SoulEntity (RUN-689), so these tests
should use a genuinely unknown field name (e.g., `custom_notes`) instead.

This audit test scans the 4 target files and asserts zero `assertions` references
remain in soul context (construction, attribute access, dict key).
"""

from pathlib import Path

# Resolve the repo root from this file's location:
# this file lives at apps/api/tests/test_run691_stale_soul_assertion_refs.py
# repo root is 4 levels up
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The 4 target files that Green must clean up
TARGET_FILES = {
    "core_auto_registration": (
        _REPO_ROOT / "packages" / "core" / "tests" / "test_run219_auto_registration.py"
    ),
    "api_soul_schema_alignment": (
        _REPO_ROOT / "apps" / "api" / "tests" / "domain" / "test_run437_soul_schema_alignment.py"
    ),
    "api_soul_update_preservation": (
        _REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_run470_soul_update_preservation.py"
    ),
    "api_soul_service": (_REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_soul_service.py"),
}


def _count_soul_assertion_refs(filepath: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) pairs where `assertions` appears in soul context.

    Matches lines that contain the word ``assertions`` used as a soul field:
    - ``assertions=[...]`` (keyword arg in constructor)
    - ``.assertions`` (attribute access)
    - ``["assertions"]`` or ``['assertions']`` (dict key access)
    - ``"assertions":`` or ``'assertions':`` (dict literal key)

    Does NOT match unrelated uses like ``assert`` statements that don't reference
    the ``assertions`` field, or imports.
    """
    import re

    # Patterns that indicate soul-field usage of "assertions"
    patterns = [
        re.compile(r"\bassertions\s*=\s*\["),  # keyword arg: assertions=[...]
        re.compile(r"\bassertions\s*=\s*None"),  # keyword arg: assertions=None
        re.compile(r"\.assertions\b"),  # attribute access: .assertions
        re.compile(r'\["assertions"\]'),  # dict key access: ["assertions"]
        re.compile(r"\['assertions'\]"),  # dict key access: ['assertions']
        re.compile(r'"assertions"\s*:'),  # dict literal key: "assertions":
        re.compile(r"'assertions'\s*:"),  # dict literal key: 'assertions':
    ]

    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(filepath.read_text().splitlines(), start=1):
        stripped = line.strip()
        # Skip pure assert statements that don't reference the field itself
        # e.g., "assert soul.id == ..." is fine, but "assert soul.assertions == ..." is a hit
        for pat in patterns:
            if pat.search(stripped):
                hits.append((lineno, stripped))
                break
    return hits


class TestStaleSoulAssertionRefsRemoved:
    """AC-1: Zero soul-assertion references remain in the 4 target test files."""

    def test_core_auto_registration_has_no_soul_assertion_refs(self):
        filepath = TARGET_FILES["core_auto_registration"]
        hits = _count_soul_assertion_refs(filepath)
        assert hits == [], (
            f"Expected zero soul-assertion references in {filepath.name}, found {len(hits)}: {hits}"
        )

    def test_api_soul_schema_alignment_has_no_soul_assertion_refs(self):
        filepath = TARGET_FILES["api_soul_schema_alignment"]
        hits = _count_soul_assertion_refs(filepath)
        assert hits == [], (
            f"Expected zero soul-assertion references in {filepath.name}, found {len(hits)}: {hits}"
        )

    def test_api_soul_update_preservation_has_no_soul_assertion_refs(self):
        filepath = TARGET_FILES["api_soul_update_preservation"]
        hits = _count_soul_assertion_refs(filepath)
        assert hits == [], (
            f"Expected zero soul-assertion references in {filepath.name}, found {len(hits)}: {hits}"
        )

    def test_api_soul_service_has_no_soul_assertion_refs(self):
        filepath = TARGET_FILES["api_soul_service"]
        hits = _count_soul_assertion_refs(filepath)
        assert hits == [], (
            f"Expected zero soul-assertion references in {filepath.name}, found {len(hits)}: {hits}"
        )

    def test_total_stale_references_across_all_files_is_zero(self):
        """Summary check: the total count across all 4 files must be zero."""
        total_hits: list[tuple[str, int, str]] = []
        for label, filepath in TARGET_FILES.items():
            for lineno, line in _count_soul_assertion_refs(filepath):
                total_hits.append((label, lineno, line))

        assert total_hits == [], (
            f"Expected zero total soul-assertion references across all target files, "
            f"found {len(total_hits)}:\n"
            + "\n".join(f"  {label}:{lineno}: {line}" for label, lineno, line in total_hits)
        )
