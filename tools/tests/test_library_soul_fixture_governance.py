"""Governance tests for library-soul fixture migration.

Owner: repo tooling governance.
Boundary: checked-in parser and API assertion fixture literals must use library
soul references instead of inline top-level soul definitions. This suite does
not execute those package test suites; it statically protects the migration
boundary so each owning workspace can run its own behavior tests.
Exit criteria: delete this suite after inline-soul fixture migration is enforced
by parser/schema validation or a documented repo tooling command with equivalent
coverage.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.governance, pytest.mark.migration]

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH = (
    _REPO_ROOT / "packages" / "core" / "tests" / "test_parser_soul_field_forwarding.py"
)

_WIRE_ASSERTION_CONFIGS_TEST_PATH = (
    _REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_wire_assertion_configs.py"
)


def _read_source(path: Path) -> str:
    """Return the full source text of *path*."""
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.Module:
    """Parse *path* into an AST module node."""
    return ast.parse(_read_source(path), filename=str(path))


def _extract_yaml_literals(path: Path) -> list[dict]:
    """Return parsed YAML dicts for YAML-looking string literals in *path*."""
    tree = _parse_ast(path)
    yaml_dicts: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if "kind: workflow" not in text and "version:" not in text:
            continue
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict) and parsed.get("kind") == "workflow":
            yaml_dicts.append(parsed)
    return yaml_dicts


def _has_module_level_xfail(path: Path) -> bool:
    """Return True if the module has a ``pytestmark = pytest.mark.xfail(...)`` assignment."""
    tree = _parse_ast(path)
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "pytestmark":
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
            for soul_key, soul_value in souls.items():
                if isinstance(soul_value, dict):
                    offending.append(d)
                    break
    return offending


class TestParserSoulForwardingFixtureGovernance:
    """Parser soul forwarding fixtures are active and library-soul based."""

    def test_parser_soul_forwarding_suite_has_no_module_level_xfail_marker(self):
        assert not _has_module_level_xfail(_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH), (
            f"{_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH.name} still has a module-level "
            f"pytestmark = pytest.mark.xfail marker - it must be removed"
        )

    def test_parser_soul_forwarding_suite_does_not_reference_xfail(self):
        source = _read_source(_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH)
        assert "xfail" not in source, (
            f"{_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH.name} still contains the string 'xfail' - "
            f"all xfail markers and references must be removed"
        )

    def test_parser_soul_forwarding_yaml_literals_use_library_soul_refs(self):
        yaml_dicts = _extract_yaml_literals(_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH)
        assert len(yaml_dicts) == 2
        offending = _yaml_fixtures_have_inline_souls(yaml_dicts)
        assert len(offending) == 0, (
            f"{_PARSER_SOUL_FIELD_FORWARDING_TEST_PATH.name} has {len(offending)} YAML fixture(s) "
            f"with inline souls: definitions - they must be converted to library soul refs"
        )


class TestAssertionConfigFixtureGovernance:
    """API assertion config fixtures use library soul refs instead of inline souls."""

    def test_assertion_config_yaml_literals_use_library_soul_refs(self):
        yaml_dicts = _extract_yaml_literals(_WIRE_ASSERTION_CONFIGS_TEST_PATH)
        assert len(yaml_dicts) == 3
        offending = _yaml_fixtures_have_inline_souls(yaml_dicts)
        assert len(offending) == 0, (
            f"{_WIRE_ASSERTION_CONFIGS_TEST_PATH.name} has {len(offending)} YAML fixture(s) "
            f"with inline souls: definitions - they must be converted to library soul refs"
        )

    def test_assertion_config_yaml_literals_do_not_embed_inline_soul_assertions(self):
        yaml_dicts = _extract_yaml_literals(_WIRE_ASSERTION_CONFIGS_TEST_PATH)
        assert len(yaml_dicts) == 3
        for yaml_dict in yaml_dicts:
            souls = yaml_dict.get("souls")
            if not isinstance(souls, dict):
                continue
            for soul_key, soul_def in souls.items():
                if isinstance(soul_def, dict) and "assertions" in soul_def:
                    pytest.fail(
                        f"Soul '{soul_key}' in {_WIRE_ASSERTION_CONFIGS_TEST_PATH.name} still has "
                        f"inline assertions - inline soul blocks must be removed"
                    )
