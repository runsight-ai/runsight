"""
Governance tests for the GUI YAML compiler test-suite ownership boundary.

Owner: tools/tests owns static repo-layout governance for cross-workspace test
structure.
Boundary: apps/gui/src/features/surface/__tests__ owns executable GUI YAML
compiler behavior coverage. This suite only checks that the old omnibus has
been replaced by behavior-named specs and GUI-owned local compiler fixtures.
Exit criteria: delete this suite once the GUI YAML compiler split is complete
and a broader repo test-layout checker enforces equivalent suite and fixture
ownership rules.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACE_TESTS = REPO_ROOT / "apps" / "gui" / "src" / "features" / "surface" / "__tests__"
LEGACY_OMNIBUS_SUITE = SURFACE_TESTS / "yamlCompiler.test.ts"
HELPER_MODULE = SURFACE_TESTS / "helpers" / "yamlCompilerFixtures.ts"

REQUIRED_SPLIT_SUITES = (
    SURFACE_TESTS / "yamlCompilerBlockFields.test.ts",
    SURFACE_TESTS / "yamlCompilerSerializationFiltering.test.ts",
    SURFACE_TESTS / "yamlCompilerWorkflowDocument.test.ts",
    SURFACE_TESTS / "yamlCompilerConditionalTransitions.test.ts",
)

REQUIRED_HELPER_EXPORTS = {
    "mockNode",
    "compileOne",
    "mockNodeWithConditions",
    "mockEdge",
    "sampleOutputConditions",
}

INLINE_HELPER_DECLARATION = re.compile(
    r"\b(?:function|const|let|var)\s+"
    r"(mockNode|compileOne|mockNodeWithConditions|mockEdge|sampleOutputConditions)\b"
)
HELPER_IMPORT = re.compile(r"\bfrom\s*['\"]\./helpers/yamlCompilerFixtures['\"]")
SKIPPED_OR_TODO_TEST = re.compile(r"\b(?:describe|it)\s*\.\s*(?:skip|todo)\s*\(")
ACTIVE_DESCRIBE = re.compile(r"\bdescribe\s*\(")
ACTIVE_IT = re.compile(r"\bit\s*\(")

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Remove JS/TS comments so commented-out suites do not satisfy governance."""
    output: list[str] = []
    index = 0
    in_line_comment = False
    in_block_comment = False
    quote: str | None = None

    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                output.append(char)
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            output.append("\n" if char == "\n" else " ")
            index += 1
            continue

        if quote:
            output.append(char)
            if char == "\\":
                if index + 1 < len(source):
                    output.append(source[index + 1])
                    index += 2
                    continue
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
            output.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        output.append(char)
        index += 1

    return "".join(output)


def _exported_names(source: str) -> set[str]:
    source = _strip_comments(source)
    names = set(
        re.findall(
            r"\bexport\s+(?:const|let|var|function|class|type|interface)\s+(\w+)",
            source,
        )
    )

    for export_block in re.findall(r"\bexport\s*\{([^}]+)\}", source, flags=re.DOTALL):
        for item in export_block.split(","):
            exported_name = item.strip().split(" as ", 1)[-1].strip()
            if exported_name:
                names.add(exported_name)

    return names


def test_gui_yaml_compiler_suite_uses_split_specs_and_local_fixtures() -> None:
    failures: list[str] = []

    if LEGACY_OMNIBUS_SUITE.exists():
        failures.append(
            f"{_relative(LEGACY_OMNIBUS_SUITE)} must be deleted after its "
            "coverage moves into behavior-named split specs."
        )

    for suite_path in REQUIRED_SPLIT_SUITES:
        if not suite_path.exists():
            failures.append(f"{_relative(suite_path)} is missing.")
            continue

        source = _strip_comments(_read(suite_path))
        if not ACTIVE_DESCRIBE.search(source):
            failures.append(f"{_relative(suite_path)} must contain an active describe(...).")
        if not ACTIVE_IT.search(source):
            failures.append(f"{_relative(suite_path)} must contain an active it(...).")
        if SKIPPED_OR_TODO_TEST.search(source):
            failures.append(
                f"{_relative(suite_path)} must not use describe.skip, it.skip, "
                "describe.todo, or it.todo."
            )
        if not HELPER_IMPORT.search(source):
            failures.append(
                f"{_relative(suite_path)} must import shared compiler fixtures from "
                "./helpers/yamlCompilerFixtures."
            )

        inline_helpers = sorted(set(INLINE_HELPER_DECLARATION.findall(source)))
        if inline_helpers:
            failures.append(
                f"{_relative(suite_path)} must not redeclare helper fixtures inline: "
                + ", ".join(inline_helpers)
            )

    if not HELPER_MODULE.exists():
        failures.append(
            f"{_relative(HELPER_MODULE)} must define GUI-owned YAML compiler test "
            "fixtures instead of keeping reusable helper setup inline in specs."
        )
    else:
        exports = _exported_names(_read(HELPER_MODULE))
        missing_exports = sorted(REQUIRED_HELPER_EXPORTS - exports)
        if missing_exports:
            failures.append(
                f"{_relative(HELPER_MODULE)} is missing required exports: "
                + ", ".join(missing_exports)
            )

    assert not failures, "\n".join(failures)
