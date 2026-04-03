"""
Red tests for RUN-647: clean up tests and fixtures for dispatch-only branching semantics.

This audit focuses on active repo-owned test and fixture surfaces that still
model the old branching block name `fanout` as a shipped concept.

Allowed exclusions:
- dedicated negative tests that prove legacy names are rejected or deleted
- this audit file itself

The current branch still has many positive `fanout` references in core, GUI,
and E2E tests/fixtures, so these tests should fail until those surfaces are
rewritten to `dispatch`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_TESTS = REPO_ROOT / "packages" / "core" / "tests"
GUI_TESTS = REPO_ROOT / "apps" / "gui" / "src" / "features" / "canvas" / "__tests__"
E2E_TESTS = REPO_ROOT / "testing" / "gui-e2e" / "tests"

EXCLUDED_FILES = {
    REPO_ROOT / "packages" / "core" / "tests" / "test_run644_dispatch_runtime_rename.py",
    REPO_ROOT / "packages" / "core" / "tests" / "test_run645_dispatch_schema_canonicalization.py",
    REPO_ROOT / "packages" / "core" / "tests" / "unit" / "test_router_delete_exit_validation.py",
    REPO_ROOT / "packages" / "core" / "tests" / "unit" / "test_exit_ports_integration.py",
    REPO_ROOT
    / "apps"
    / "gui"
    / "src"
    / "features"
    / "canvas"
    / "__tests__"
    / "legacyCleanup.test.ts",
    REPO_ROOT
    / "apps"
    / "gui"
    / "src"
    / "features"
    / "canvas"
    / "__tests__"
    / "yamlCompiler.test.ts",
    REPO_ROOT / "apps" / "gui" / "src" / "features" / "canvas" / "__tests__" / "yamlParser.test.ts",
    REPO_ROOT
    / "apps"
    / "gui"
    / "src"
    / "features"
    / "canvas"
    / "__tests__"
    / "yamlRoundTrip.test.ts",
    Path(__file__).resolve(),
}

SOURCE_SUFFIXES = {".py", ".ts", ".tsx"}


def _scan_for_fanout(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if path.resolve() in EXCLUDED_FILES:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        for lineno, line in enumerate(source.splitlines(), start=1):
            if re.search(r"\bfanout\b", line, re.IGNORECASE):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    return hits


def _format_hits(hits: list[str], *, limit: int = 25) -> str:
    preview = hits[:limit]
    message = "\n".join(preview)
    remaining = len(hits) - len(preview)
    if remaining > 0:
        message += f"\n... and {remaining} more matching lines"
    return message


class TestCoreTestsAndFixtures:
    """Core tests still model fanout as a shipped branching concept."""

    def test_core_tests_and_fixtures_no_longer_use_fanout(self):
        hits = _scan_for_fanout(CORE_TESTS)
        assert not hits, (
            "Core tests/fixtures still contain legacy fanout modeling:\n" + _format_hits(hits)
        )


class TestGuiCanvasTestsAndFixtures:
    """GUI canvas tests still model fanout as a shipped branching concept."""

    def test_gui_canvas_tests_and_fixtures_no_longer_use_fanout(self):
        hits = _scan_for_fanout(GUI_TESTS)
        assert not hits, (
            "GUI canvas tests/fixtures still contain legacy fanout modeling:\n" + _format_hits(hits)
        )


class TestGuiE2ETestsAndFixtures:
    """GUI E2E tests still model fanout as a shipped branching concept."""

    def test_gui_e2e_tests_and_fixtures_no_longer_use_fanout(self):
        hits = _scan_for_fanout(E2E_TESTS)
        assert not hits, (
            "GUI E2E tests/fixtures still contain legacy fanout modeling:\n" + _format_hits(hits)
        )
