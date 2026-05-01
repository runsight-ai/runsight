"""Governance tests for API simulation branch fixture ownership.

Owner: tools/tests owns temporary static checks for API test fixture ownership
migrations.
Boundary: reusable workflow YAML payloads for
apps/api/tests/logic/test_sim_branches.py belong under apps/api/tests/fixtures.
This suite inspects only repo-owned API test source, not runtime/user-authored
state.
Exit criteria: delete this suite once the reusable simulation branch YAML sample
has been externalized to an API-owned fixture file and loaded through a helper
or fixture while preserving the branch behavior coverage.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_BRANCHES_TEST = REPO_ROOT / "apps" / "api" / "tests" / "logic" / "test_sim_branches.py"
API_SIM_BRANCH_FIXTURE_ROOT = REPO_ROOT / "apps" / "api" / "tests" / "fixtures" / "sim_branches"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class ModuleYamlSample:
    name: str
    line_number: int
    workflow_name: str
    step_count: int


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


def _sim_branch_sample_shape(text: str) -> tuple[str, int] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None

    workflow_name = parsed.get("name")
    steps = parsed.get("steps")
    has_sim_branch_sample_shape = (
        isinstance(workflow_name, str)
        and isinstance(steps, list)
        and all(isinstance(step, dict) for step in steps)
    )
    if not has_sim_branch_sample_shape:
        return None

    return workflow_name, len(steps)


def _module_level_reusable_yaml_samples(path: Path) -> list[ModuleYamlSample]:
    samples: list[ModuleYamlSample] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        targets = _assignment_targets(statement)
        reusable_yaml_targets = [
            target
            for target in targets
            if "YAML" in target.upper()
            and ("SAMPLE" in target.upper() or "FIXTURE" in target.upper())
        ]
        if not reusable_yaml_targets:
            continue

        sample_shape = _sim_branch_sample_shape(value)
        if sample_shape is None:
            continue

        workflow_name, step_count = sample_shape
        samples.extend(
            ModuleYamlSample(
                name=target,
                line_number=statement.lineno,
                workflow_name=workflow_name,
                step_count=step_count,
            )
            for target in reusable_yaml_targets
        )
    return samples


def test_api_sim_branches_suite_uses_api_owned_yaml_fixtures() -> None:
    """Owner/boundary/exit: reusable sim branch YAML samples are API-owned fixtures."""
    samples = _module_level_reusable_yaml_samples(SIM_BRANCHES_TEST)

    assert samples == [], (
        f"{_relative(SIM_BRANCHES_TEST)} must not define reusable module-level YAML "
        "sample payloads for simulation branch behavior tests. Move reusable sim "
        f"branch YAML content to {_relative(API_SIM_BRANCH_FIXTURE_ROOT)} or a "
        "similarly behavior-named API fixture directory, then load it through a "
        "small helper or fixture in the test module. This check only flags "
        "module-level YAML-like sample payloads by assignment name and YAML shape; "
        "scalar constants such as branch regex patterns remain allowed. Found:\n"
        + "\n".join(
            f"  - {sample.name} at line {sample.line_number} "
            f"(workflow name: {sample.workflow_name}, steps: {sample.step_count})"
            for sample in samples
        )
    )
