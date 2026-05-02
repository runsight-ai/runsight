"""Smoke governance for the GUI YAML compiler test-suite boundary.

Owner: tools/tests owns static repo-layout governance for cross-workspace test
structure.
Boundary: apps/gui/src/features/surface/__tests__ owns executable YAML compiler
behavior coverage, and reusable compiler fixtures stay in that workspace's
helpers/ directory.
Exit criteria: delete this suite once a broader repo test-layout checker
enforces equivalent split-suite and local-fixture ownership rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACE_TESTS = REPO_ROOT / "apps" / "gui" / "src" / "features" / "surface" / "__tests__"
LEGACY_OMNIBUS_SUITE = SURFACE_TESTS / "yamlCompiler.test.ts"
HELPER_MODULE = SURFACE_TESTS / "helpers" / "yamlCompilerFixtures.ts"

YAML_COMPILER_SPLIT_SPECS = (
    SURFACE_TESTS / "yamlCompilerBlockFields.test.ts",
    SURFACE_TESTS / "yamlCompilerSerializationFiltering.test.ts",
    SURFACE_TESTS / "yamlCompilerWorkflowDocument.test.ts",
    SURFACE_TESTS / "yamlCompilerConditionalTransitions.test.ts",
)

YAML_COMPILER_HELPERS = (
    "mockNode",
    "compileOne",
    "mockNodeWithConditions",
    "mockEdge",
    "sampleOutputConditions",
)

COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
HELPER_IMPORT = re.compile(r"\bfrom\s*['\"]\./helpers/yamlCompilerFixtures['\"]")
INLINE_HELPER_DECLARATION = re.compile(
    r"\b(?:function|const|let|var)\s+("
    + "|".join(re.escape(name) for name in YAML_COMPILER_HELPERS)
    + r")\b"
)
EXPORT_DECLARATION = re.compile(
    r"\bexport\s+(?:const|let|var|function|class|type|interface)\s+(\w+)"
)
EXPORT_BLOCK = re.compile(r"\bexport\s*\{([^}]+)\}", re.DOTALL)

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read_source(path: Path) -> str:
    return COMMENT.sub("", path.read_text(encoding="utf-8"))


def _exported_names(source: str) -> set[str]:
    names = set(EXPORT_DECLARATION.findall(source))

    for export_block in EXPORT_BLOCK.findall(source):
        for item in export_block.split(","):
            exported_name = item.strip().split(" as ", 1)[-1].strip()
            if exported_name:
                names.add(exported_name)

    return names


def test_gui_yaml_compiler_split_specs_use_local_fixtures() -> None:
    """Owner/boundary/exit: keep YAML compiler split specs on local helpers."""
    failures: list[str] = []

    if LEGACY_OMNIBUS_SUITE.exists():
        failures.append(f"{_relative(LEGACY_OMNIBUS_SUITE)} must stay deleted.")

    for spec_path in YAML_COMPILER_SPLIT_SPECS:
        if not spec_path.is_file():
            failures.append(f"{_relative(spec_path)} is missing.")
            continue

        source = _read_source(spec_path)
        if not HELPER_IMPORT.search(source):
            failures.append(
                f"{_relative(spec_path)} must import shared compiler fixtures from "
                "./helpers/yamlCompilerFixtures."
            )

        inline_helpers = sorted(set(INLINE_HELPER_DECLARATION.findall(source)))
        if inline_helpers:
            failures.append(
                f"{_relative(spec_path)} must not redeclare helper fixtures inline: "
                + ", ".join(inline_helpers)
            )

    if not HELPER_MODULE.is_file():
        failures.append(f"{_relative(HELPER_MODULE)} is missing.")
    else:
        missing_exports = sorted(
            set(YAML_COMPILER_HELPERS) - _exported_names(_read_source(HELPER_MODULE))
        )
        if missing_exports:
            failures.append(
                f"{_relative(HELPER_MODULE)} is missing exports: " + ", ".join(missing_exports)
            )

    assert not failures, "\n".join(failures)
