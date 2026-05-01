"""Governance tests for core eval runner fixture ownership.

Owner: tools/tests owns temporary static checks for cross-workspace test
fixture ownership migrations.
Boundary: reusable eval runner workflow fixtures belong under
packages/core/tests/fixtures/eval and packages/core/tests/test_eval_runner.py
must load them through eval_fixture_helpers instead of defining module-level
YAML constants. Local inline YAML inside a single edge-case test remains
package test ownership and is intentionally not scanned here.
Exit criteria: delete this suite once the eval runner workflow fixtures have
been externalized and the core eval runner tests have stable fixture-loading
coverage in the owning package suite.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_RUNNER_TEST = REPO_ROOT / "packages" / "core" / "tests" / "test_eval_runner.py"
EVAL_FIXTURE_DIR = REPO_ROOT / "packages" / "core" / "tests" / "fixtures" / "eval"

EXPECTED_EVAL_RUNNER_FIXTURES = [
    "eval-runner-two-case.yaml",
    "eval-runner-fixture-case.yaml",
    "eval-runner-low-threshold.yaml",
    "eval-runner-two-block.yaml",
    "eval-runner-no-expected-case.yaml",
    "eval-runner-no-fixtures-no-executor.yaml",
]

MODULE_LEVEL_YAML_CONSTANT = re.compile(r"^_[A-Z0-9_]*YAML$")

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _eval_runner_tree() -> ast.Module:
    return ast.parse(EVAL_RUNNER_TEST.read_text(encoding="utf-8"))


def _string_constant_names(statement: ast.stmt) -> list[str]:
    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
        if not isinstance(statement.value.value, str):
            return []

        return [
            target.id
            for target in statement.targets
            if isinstance(target, ast.Name) and MODULE_LEVEL_YAML_CONSTANT.match(target.id)
        ]

    if isinstance(statement, ast.AnnAssign) and isinstance(statement.value, ast.Constant):
        if not isinstance(statement.value.value, str):
            return []
        if isinstance(statement.target, ast.Name) and MODULE_LEVEL_YAML_CONSTANT.match(
            statement.target.id
        ):
            return [statement.target.id]

    return []


def test_eval_runner_reusable_workflow_fixtures_live_in_eval_fixture_directory() -> None:
    missing = [
        _relative(EVAL_FIXTURE_DIR / fixture_name)
        for fixture_name in EXPECTED_EVAL_RUNNER_FIXTURES
        if not (EVAL_FIXTURE_DIR / fixture_name).is_file()
    ]

    assert missing == [], "Missing eval runner workflow fixture files:\n" + "\n".join(
        f"  - {path}" for path in missing
    )


def test_eval_runner_loads_external_workflow_fixtures_through_helper() -> None:
    imports_helper = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "eval_fixture_helpers"
        and any(alias.name == "eval_fixture_text" for alias in statement.names)
        for statement in _eval_runner_tree().body
    )

    assert imports_helper, (
        f"{_relative(EVAL_RUNNER_TEST)} must import eval_fixture_text from "
        "eval_fixture_helpers to load reusable eval workflow fixtures."
    )


def test_eval_runner_does_not_define_reusable_module_level_yaml_constants() -> None:
    constants = [
        name for statement in _eval_runner_tree().body for name in _string_constant_names(statement)
    ]

    assert constants == [], (
        f"{_relative(EVAL_RUNNER_TEST)} must not define reusable module-level "
        "_...YAML string constants. Move reusable eval runner workflow YAML to "
        "packages/core/tests/fixtures/eval and load it with eval_fixture_text. "
        f"Found: {', '.join(constants)}"
    )
