"""Governance tests for parser tool-validation suite decomposition.

Owner: tools/tests owns temporary static checks for core parser test-suite
decomposition migrations.
Boundary: packages/core/tests/unit/test_parser_tool_validation.py should stop
being the behavior owner for declared-tool whitelist, custom tool discovery,
and delegate exit-schema contracts. Those behavior tests should live in
owner-specific core unit suites and use package-local builders or fixtures for
repeated workflow YAML and custom tool metadata.
Exit criteria: delete this suite once parser tool validation behavior has been
split into ordinary owner-specific suites with reusable package-local
fixture/builders, and that layout is enforced by the owning package tests or
repo tooling.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_UNIT_TEST_ROOT = REPO_ROOT / "packages" / "core" / "tests" / "unit"
LEGACY_PARSER_TOOL_VALIDATION_SUITE = CORE_UNIT_TEST_ROOT / "test_parser_tool_validation.py"

REQUIRED_OWNER_SUITES = {
    "parser declared-tool whitelist": CORE_UNIT_TEST_ROOT
    / "test_parser_declared_tool_whitelist.py",
    "parser custom tool discovery contract": CORE_UNIT_TEST_ROOT
    / "test_parser_custom_tool_discovery_contract.py",
    "delegate tool exit schema": CORE_UNIT_TEST_ROOT / "test_parser_delegate_exit_schema.py",
}

MAX_LEGACY_TESTS = 12
MAX_LEGACY_TEST_CLASSES = 3
MAX_LEGACY_EFFECTIVE_LINES = 650
MAX_STRUCTURED_LITERAL_COUNT_PER_BEHAVIOR_SUITE = 12
MAX_STRUCTURED_LITERAL_LINES_PER_BEHAVIOR_SUITE = 120
STRUCTURED_LITERAL_MARKERS = (
    "tools:",
    "souls:",
    "blocks:",
    "executor:",
    "code: |",
    "request:",
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class SuiteMetrics:
    path: Path
    effective_lines: int
    test_classes: tuple[str, ...]
    test_count: int


@dataclass(frozen=True)
class StructuredLiteralUse:
    path: Path
    test_name: str
    line_number: int
    line_count: int
    markers: tuple[str, ...]


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _effective_line_count(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _suite_metrics(path: Path) -> SuiteMetrics:
    tree = _source_tree(path)
    test_classes = tuple(
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
    )
    test_count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    return SuiteMetrics(
        path=path,
        effective_lines=_effective_line_count(path),
        test_classes=test_classes,
        test_count=test_count,
    )


def _test_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def _structured_literal_markers(text: str) -> tuple[str, ...]:
    if len(text.splitlines()) < 2:
        return ()
    return tuple(marker for marker in STRUCTURED_LITERAL_MARKERS if marker in text)


def _structured_literal_uses(path: Path) -> list[StructuredLiteralUse]:
    uses: list[StructuredLiteralUse] = []

    for function in _test_functions(_source_tree(path)):
        for node in ast.walk(function):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue

            markers = _structured_literal_markers(node.value)
            if not markers:
                continue

            uses.append(
                StructuredLiteralUse(
                    path=path,
                    test_name=function.name,
                    line_number=node.lineno,
                    line_count=len(node.value.splitlines()),
                    markers=markers,
                )
            )

    return sorted(uses, key=lambda use: (use.path, use.line_number))


def _behavior_suite_paths() -> tuple[Path, ...]:
    return (
        LEGACY_PARSER_TOOL_VALIDATION_SUITE,
        *(path for path in REQUIRED_OWNER_SUITES.values() if path.exists()),
    )


def test_parser_tool_validation_behavior_has_owner_specific_suites() -> None:
    """Owner/boundary/exit: parser tool contracts should not stay in one god-object suite."""
    missing_owner_suites = [
        f"{owner}: {_relative(path)}"
        for owner, path in REQUIRED_OWNER_SUITES.items()
        if not path.exists()
    ]
    legacy_metrics = _suite_metrics(LEGACY_PARSER_TOOL_VALIDATION_SUITE)

    violations: list[str] = []
    if missing_owner_suites:
        violations.append(
            "missing owner-specific parser tool validation suites:\n"
            + "\n".join(f"  - {suite}" for suite in missing_owner_suites)
        )
    if legacy_metrics.test_count > MAX_LEGACY_TESTS:
        violations.append(
            f"{_relative(legacy_metrics.path)} still owns {legacy_metrics.test_count} "
            f"tests; keep any residual compatibility suite below {MAX_LEGACY_TESTS} "
            "tests after moving behavior coverage to owner-specific suites"
        )
    if len(legacy_metrics.test_classes) > MAX_LEGACY_TEST_CLASSES:
        violations.append(
            f"{_relative(legacy_metrics.path)} still owns "
            f"{len(legacy_metrics.test_classes)} Test* classes "
            f"({', '.join(legacy_metrics.test_classes)}); keep the residual suite "
            f"below {MAX_LEGACY_TEST_CLASSES} behavior-owner groups"
        )
    if legacy_metrics.effective_lines > MAX_LEGACY_EFFECTIVE_LINES:
        violations.append(
            f"{_relative(legacy_metrics.path)} still has "
            f"{legacy_metrics.effective_lines} effective source lines; split the "
            "normal behavior coverage instead of preserving a large catch-all suite"
        )

    assert violations == [], (
        "Parser tool validation behavior must be split by owner. Expected "
        "ordinary core unit suites for the declared-tool whitelist, custom tool "
        "discovery contract, and delegate exit schema, with only a small "
        "residual compatibility suite left at "
        f"{_relative(LEGACY_PARSER_TOOL_VALIDATION_SUITE)}. Found:\n"
        + "\n".join(f"- {violation}" for violation in violations)
    )


def test_parser_tool_validation_structured_fixtures_are_externalized() -> None:
    """Owner/boundary/exit: behavior suites should use builders for bulky YAML/tool code."""
    violations: list[str] = []

    for path in _behavior_suite_paths():
        uses = _structured_literal_uses(path)
        literal_count = len(uses)
        literal_lines = sum(use.line_count for use in uses)
        if (
            literal_count <= MAX_STRUCTURED_LITERAL_COUNT_PER_BEHAVIOR_SUITE
            and literal_lines <= MAX_STRUCTURED_LITERAL_LINES_PER_BEHAVIOR_SUITE
        ):
            continue

        examples = "\n".join(
            "  - "
            f"line {use.line_number}: {use.test_name} has {use.line_count} "
            f"structured literal lines ({', '.join(use.markers)})"
            for use in uses[:10]
        )
        remaining = literal_count - min(literal_count, 10)
        if remaining:
            examples += f"\n  - ... {remaining} more structured literals"

        violations.append(
            f"{_relative(path)} keeps {literal_count} structured literals "
            f"covering {literal_lines} lines in behavior tests; move repeated "
            "workflow YAML and custom tool metadata into package-local builders "
            "or fixtures. Examples:\n" + examples
        )

    assert violations == [], (
        "Parser tool validation behavior suites must not carry large repeated "
        "inline YAML or custom tool metadata. Keep behavior tests focused on "
        "assertions and move bulky setup into package-local builders or "
        "fixtures under packages/core/tests or packages/core/tests/unit. Found:\n"
        + "\n".join(f"- {violation}" for violation in violations)
    )
