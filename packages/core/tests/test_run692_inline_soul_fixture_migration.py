"""Red tests for RUN-692: inline-soul test fixture migration.

Verifies that:
1. test_run468 has no module-level xfail marker and its tests pass
2. test_run347 YAML fixtures use library soul refs, not inline souls: blocks
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths to the two files under migration
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]

_TEST_RUN468_PATH = (
    _REPO_ROOT / "packages" / "core" / "tests" / "test_run468_parser_soul_field_forwarding.py"
)

_TEST_RUN347_PATH = (
    _REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_run347_wire_assertion_configs.py"
)


# ===================================================================
# Helpers
# ===================================================================


def _read_source(path: Path) -> str:
    """Return the full source text of *path*."""
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.Module:
    """Parse *path* into an AST module node."""
    return ast.parse(_read_source(path), filename=str(path))


def _extract_yaml_constants(path: Path) -> list[dict]:
    """Return parsed YAML dicts for every module-level string constant."""
    tree = _parse_ast(path)
    yaml_dicts: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # Module-level constant assignment like YAML_FOO = "..."
            if isinstance(node.value, (ast.Constant,)) and isinstance(node.value.value, str):
                try:
                    parsed = yaml.safe_load(node.value.value)
                    if isinstance(parsed, dict):
                        yaml_dicts.append(parsed)
                except yaml.YAMLError:
                    continue
        # Also handle JoinedStr or multiline strings assigned at module scope
    return yaml_dicts


def _has_module_level_xfail(path: Path) -> bool:
    """Return True if the module has a ``pytestmark = pytest.mark.xfail(...)`` assignment."""
    tree = _parse_ast(path)
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "pytestmark":
                # Check if the value involves xfail
                source_segment = ast.get_source_segment(_read_source(path), node)
                if source_segment and "xfail" in source_segment:
                    return True
    return False


def _yaml_fixtures_have_inline_souls(yaml_dicts: list[dict]) -> list[dict]:
    """Return YAML dicts that have a ``souls:`` section with populated definitions."""
    offending = []
    for d in yaml_dicts:
        souls = d.get("souls")
        if isinstance(souls, dict) and len(souls) > 0:
            # Check if any value is a dict (i.e., an inline soul definition, not just a ref)
            for soul_key, soul_value in souls.items():
                if isinstance(soul_value, dict):
                    offending.append(d)
                    break
    return offending


# ===================================================================
# AC-1: test_run468 — no xfail, tests pass
# ===================================================================


class TestRun468NoXfailMarker:
    """test_run468_parser_soul_field_forwarding.py must not have a module-level xfail marker."""

    def test_no_module_level_xfail_marker(self):
        """The pytestmark = pytest.mark.xfail(...) line must be removed."""
        assert not _has_module_level_xfail(_TEST_RUN468_PATH), (
            f"{_TEST_RUN468_PATH.name} still has a module-level "
            f"pytestmark = pytest.mark.xfail marker — it must be removed"
        )

    def test_source_does_not_contain_xfail_string(self):
        """Extra safety: the string 'xfail' should not appear anywhere in the module."""
        source = _read_source(_TEST_RUN468_PATH)
        assert "xfail" not in source, (
            f"{_TEST_RUN468_PATH.name} still contains the string 'xfail' — "
            f"all xfail markers and references must be removed"
        )


class TestRun468FixturesUseLibrarySouls:
    """test_run468 YAML fixtures must use library soul refs, not inline souls."""

    def test_yaml_fixtures_have_no_inline_soul_definitions(self):
        """YAML constants must not define souls inline in a top-level souls: block."""
        yaml_dicts = _extract_yaml_constants(_TEST_RUN468_PATH)
        offending = _yaml_fixtures_have_inline_souls(yaml_dicts)
        assert len(offending) == 0, (
            f"{_TEST_RUN468_PATH.name} has {len(offending)} YAML fixture(s) "
            f"with inline souls: definitions — they must be converted to library soul refs"
        )


class TestRun468TestsPass:
    """test_run468 tests must actually pass (not xfail, not error)."""

    def test_run468_tests_pass_without_xfail(self):
        """Run the test file via subprocess and verify all tests pass."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(_TEST_RUN468_PATH),
                "-v",
                "--tb=short",
                "--no-header",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
        )
        # The test run must succeed (exit code 0) with no xfailed or failed tests
        assert result.returncode == 0, (
            f"test_run468 tests did not pass (exit code {result.returncode}).\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        # Verify no xfailed results in the output
        assert "xfailed" not in result.stdout.lower(), (
            f"test_run468 still has xfailed tests in output:\n{result.stdout}"
        )


# ===================================================================
# AC-2: test_run347 — library soul refs, no inline souls
# ===================================================================


class TestRun347FixturesUseLibrarySouls:
    """test_run347_wire_assertion_configs.py must use soul_ref without inline souls."""

    def test_yaml_fixtures_have_no_inline_soul_definitions(self):
        """YAML constants must not define souls inline in a top-level souls: block."""
        yaml_dicts = _extract_yaml_constants(_TEST_RUN347_PATH)
        offending = _yaml_fixtures_have_inline_souls(yaml_dicts)
        assert len(offending) == 0, (
            f"{_TEST_RUN347_PATH.name} has {len(offending)} YAML fixture(s) "
            f"with inline souls: definitions — they must be converted to library soul refs"
        )

    def test_run347_tests_pass_after_migration(self):
        """Run test_run347 via subprocess and verify all tests pass.

        This is the AC-2 counterpart to TestRun468TestsPass: after inline soul
        fixtures are migrated to library soul refs, the test_run347 suite must
        still pass end-to-end.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(_TEST_RUN347_PATH),
                "-v",
                "--tb=short",
                "--no-header",
                "-q",
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"test_run347 tests did not pass (exit code {result.returncode}).\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_no_soul_level_assertions_remain_in_valid_fixtures(self):
        """Valid YAML fixtures must not have assertions inside soul definitions.

        Note: YAML_INVALID_SOUL_ASSERTIONS and YAML_INVALID_SOUL_AND_BLOCK_ASSERTIONS
        are intentionally invalid fixtures that test parser rejection. Those are expected
        to contain soul-level assertions. But if inline souls: blocks are removed,
        the invalid fixtures must be restructured to test the same validation
        without inline soul definitions.
        """
        yaml_dicts = _extract_yaml_constants(_TEST_RUN347_PATH)
        for yaml_dict in yaml_dicts:
            souls = yaml_dict.get("souls")
            if not isinstance(souls, dict):
                continue
            for soul_key, soul_def in souls.items():
                if isinstance(soul_def, dict) and "assertions" in soul_def:
                    pytest.fail(
                        f"Soul '{soul_key}' in {_TEST_RUN347_PATH.name} still has "
                        f"inline assertions — inline soul blocks must be removed"
                    )
