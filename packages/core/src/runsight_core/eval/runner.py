"""Offline eval runner for workflow test cases (RUN-695)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from runsight_core.assertions.base import AssertionContext
from runsight_core.assertions.registry import register_custom_assertions, run_assertions
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.discovery import AssertionScanner
from runsight_core.yaml.schema import EvalSectionDef


@dataclass
class EvalCaseResult:
    """Result of evaluating a single test case."""

    case_id: str
    passed: bool
    score: float
    block_results: dict[str, AssertionsResult] = field(default_factory=dict)


@dataclass
class EvalSuiteResult:
    """Aggregate result of all eval cases in a workflow."""

    passed: bool
    score: float
    threshold: float
    case_results: list[EvalCaseResult] = field(default_factory=list)


def _build_eval_context(block_id: str, output: str) -> AssertionContext:
    """Build a minimal AssertionContext for eval mode."""
    return AssertionContext(
        output=output,
        prompt="",
        prompt_hash="",
        soul_id="",
        soul_version="",
        block_id=block_id,
        block_type="",
        cost_usd=0.0,
        total_tokens=0,
        latency_ms=0.0,
        variables={},
        run_id="",
        workflow_id="",
    )


def _has_fixtures_for_all_expected(
    fixtures: dict[str, str] | None,
    expected: dict[str, list[dict[str, Any]]] | None,
) -> bool:
    """Return True if fixtures cover every block_id present in expected."""
    if not expected:
        return True
    if not fixtures:
        return False
    return all(block_id in fixtures for block_id in expected)


def _find_project_root(start: Path) -> str:
    """Walk up from *start* to find the directory that contains ``custom/``."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        custom_dir = candidate / "custom"
        if not custom_dir.is_dir():
            continue
        if candidate == current:
            return str(candidate)
        try:
            current.relative_to(custom_dir)
        except ValueError:
            continue
        return str(candidate)
    return str(start)


def _load_eval_workflow_source(workflow_yaml: str) -> tuple[dict[str, Any], str | None]:
    """Load eval workflow input from either raw YAML content or a workflow file path."""
    stripped = workflow_yaml.strip()
    is_file_path = (
        "\n" not in stripped
        and stripped.endswith((".yaml", ".yml", ".json"))
        and Path(stripped).exists()
    )
    if is_file_path:
        workflow_path = Path(stripped).resolve()
        with open(workflow_path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle), _find_project_root(workflow_path.parent)
    return yaml.safe_load(workflow_yaml), None


async def run_eval(
    workflow_yaml: str,
    *,
    executor: Callable[..., Any] | None = None,
) -> EvalSuiteResult:
    """Run offline eval cases defined in a workflow's eval section.

    For each case:
    - If fixtures cover all expected blocks, uses fixtures (no executor call).
    - Otherwise, calls executor to get a WorkflowState.
    - Runs assertions per block and aggregates scores.
    """
    raw, workflow_base_dir = _load_eval_workflow_source(workflow_yaml)
    if workflow_base_dir is not None:
        assertion_index = AssertionScanner(workflow_base_dir).scan()
        register_custom_assertions(assertion_index)
    eval_raw = raw.get("eval")
    if eval_raw is None:
        raise ValueError("Workflow YAML has no eval section")

    eval_section = EvalSectionDef.model_validate(eval_raw)
    threshold = eval_section.threshold if eval_section.threshold is not None else 1.0
    case_results: list[EvalCaseResult] = []

    for case in eval_section.cases:
        expected = case.expected or {}
        fixtures = case.fixtures
        inputs = case.inputs or {}

        if _has_fixtures_for_all_expected(fixtures, expected):
            # Fixture mode: build WorkflowState from fixtures
            state = WorkflowState()
            if fixtures:
                for block_id, output_text in fixtures.items():
                    state.results[block_id] = BlockResult(output=output_text)
        else:
            # Executor mode
            if executor is None:
                raise RuntimeError(
                    f"Case {case.id!r} requires an executor (no fixtures for all "
                    f"expected blocks) but no executor was provided."
                )
            state = await executor(raw, inputs)

        # Run assertions for each block in expected
        block_results: dict[str, AssertionsResult] = {}
        for block_id, assertion_configs in expected.items():
            output = state.results[block_id].output
            context = _build_eval_context(block_id, output)
            agg = await run_assertions(assertion_configs, output=output, context=context)
            block_results[block_id] = agg

        # Compute case score as average of block aggregate_scores
        if block_results:
            case_score = sum(br.aggregate_score for br in block_results.values()) / len(
                block_results
            )
            case_passed = all(br.passed() for br in block_results.values())
        else:
            case_score = 1.0
            case_passed = True

        case_results.append(
            EvalCaseResult(
                case_id=case.id,
                passed=case_passed,
                score=case_score,
                block_results=block_results,
            )
        )

    # Compute suite score as average of case scores
    if case_results:
        suite_score = sum(cr.score for cr in case_results) / len(case_results)
    else:
        suite_score = 0.0

    suite_passed = suite_score >= threshold

    return EvalSuiteResult(
        passed=suite_passed,
        score=suite_score,
        threshold=threshold,
        case_results=case_results,
    )
