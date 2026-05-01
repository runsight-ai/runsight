"""Governance tests for core parser YAML helper fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: reusable parser YAML sections in packages/core/tests/parser_yaml_helpers.py
should be assembled by helper functions or package fixtures, not stored as
module-level triple-quoted YAML constants. This suite inspects only repo-owned
core test helper source, not runtime or user state.
Exit criteria: delete this suite once parser_yaml_helpers.py exposes reusable
YAML sections through builders such as researcher_soul_yaml() and
researcher_reviewer_souls_yaml(), using soul_entry_yaml()/souls_yaml(), or
through package-owned fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSER_YAML_HELPERS = REPO_ROOT / "packages" / "core" / "tests" / "parser_yaml_helpers.py"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleYamlSectionConstant:
    name: str
    line_number: int
    top_level_key: str
    entry_names: tuple[str, ...]


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _assignment_targets(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _string_assignment_value(statement: ast.stmt) -> str | None:
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None
    if not isinstance(statement.value, ast.Constant) or not isinstance(statement.value.value, str):
        return None
    return statement.value.value


def _structured_yaml_section_details(text: str) -> tuple[str, tuple[str, ...]] | None:
    try:
        parsed = yaml.safe_load(dedent(text))
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    for top_level_key in ("souls",):
        section = parsed.get(top_level_key)
        if not isinstance(section, dict):
            continue

        entry_names = tuple(sorted(name for name in section if isinstance(name, str)))
        return top_level_key, entry_names

    return None


def _module_level_yaml_section_constants(path: Path) -> list[ModuleYamlSectionConstant]:
    constants: list[ModuleYamlSectionConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _structured_yaml_section_details(value)
        if details is None:
            continue

        top_level_key, entry_names = details
        constants.extend(
            ModuleYamlSectionConstant(
                name=name,
                line_number=statement.lineno,
                top_level_key=top_level_key,
                entry_names=entry_names,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def test_core_parser_yaml_helpers_use_builders_for_reusable_yaml_sections() -> None:
    """Reusable parser YAML sections should be functions or package fixtures."""
    constants = _module_level_yaml_section_constants(PARSER_YAML_HELPERS)

    assert constants == [], (
        f"{_relative(PARSER_YAML_HELPERS)} must not define reusable "
        "module-level structured YAML section constants. Build reusable parser "
        "YAML sections with helper functions such as researcher_soul_yaml() and "
        "researcher_reviewer_souls_yaml() using soul_entry_yaml()/souls_yaml(), "
        "or move reusable payloads to package-owned fixtures. Dict constants "
        "used as data payloads, small scalar literals, and builder functions "
        "that return YAML may remain. Found:\n"
        + "\n".join(
            "  - "
            f"{constant.name} at line {constant.line_number} "
            f"(top-level {constant.top_level_key}: "
            f"{', '.join(constant.entry_names) or '<empty>'})"
            for constant in constants
        )
    )
