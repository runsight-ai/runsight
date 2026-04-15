"""RUN-800: end-to-end custom assertion coverage for offline eval runner."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import runsight_core.assertions.deterministic  # noqa: F401
import yaml
from runsight_core.eval.runner import run_eval


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _write_assertion(
    base_dir: Path,
    *,
    stem: str,
    returns: str,
    code: str,
    params: dict[str, Any] | None = None,
) -> None:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": stem,
        "kind": "assertion",
        "version": "1.0",
        "name": stem.replace("_", " ").title(),
        "description": f"Custom assertion {stem}",
        "returns": returns,
        "source": f"{stem}.py",
    }
    if params is not None:
        manifest["params"] = params
    _write_yaml(assertions_dir / f"{stem}.yaml", manifest)
    (assertions_dir / f"{stem}.py").write_text(dedent(code), encoding="utf-8")


def _write_eval_workflow(
    base_dir: Path,
    *,
    expected_assertions: list[dict[str, Any]],
    fixture_output: str = "calm response",
) -> Path:
    workflow = {
        "id": "run800-eval-flow",
        "kind": "workflow",
        "version": "1.0",
        "config": {"model_name": "gpt-4o"},
        "blocks": {
            "analyze": {
                "type": "code",
                "code": "def main(data):\n    return 'unused in fixture mode'\n",
            }
        },
        "workflow": {
            "name": "run800_eval_flow",
            "entry": "analyze",
            "transitions": [{"from": "analyze", "to": None}],
        },
        "eval": {
            "threshold": 0.5,
            "cases": [
                {
                    "id": "custom_case",
                    "fixtures": {"analyze": fixture_output},
                    "expected": {"analyze": expected_assertions},
                }
            ],
        },
    }
    return _write_yaml(base_dir / "workflow.yaml", workflow)


class TestRunEvalCustomAssertionsE2E:
    @pytest.mark.asyncio
    async def test_run_eval_path_discovers_promptfoo_custom_assertion_with_config_and_builtin(
        self, tmp_path: Path
    ):
        _write_assertion(
            tmp_path,
            stem="tone_check",
            returns="grading_result",
            code="""
            def get_assert(output, context):
                config = context.get("config", {})
                return {
                    "pass": output.startswith(config.get("prefix", "")),
                    "score": 0.9,
                    "reason": f"prefix={config.get('prefix', '')}",
                }
            """,
        )
        workflow_path = _write_eval_workflow(
            tmp_path,
            expected_assertions=[
                {
                    "type": "custom:tone_check",
                    "config": {"prefix": "calm"},
                },
                {
                    "type": "contains",
                    "value": "response",
                },
            ],
        )

        result = await run_eval(str(workflow_path))

        assert result.passed is True
        analyze_results = result.case_results[0].block_results["analyze"].results
        assert len(analyze_results) == 2
        assert analyze_results[0].assertion_type == "custom:tone_check"
        assert analyze_results[0].passed is True
        assert analyze_results[0].score == pytest.approx(0.9)
        assert analyze_results[1].passed is True

    @pytest.mark.asyncio
    async def test_run_eval_supports_not_prefixed_custom_assertions(self, tmp_path: Path):
        _write_assertion(
            tmp_path,
            stem="blocked_word",
            returns="bool",
            code="""
            def get_assert(output, context):
                config = context.get("config", {})
                return config.get("blocked") in output
            """,
        )
        workflow_path = _write_eval_workflow(
            tmp_path,
            expected_assertions=[
                {
                    "type": "not-custom:blocked_word",
                    "config": {"blocked": "storm"},
                }
            ],
            fixture_output="calm response",
        )

        result = await run_eval(str(workflow_path))

        grading = result.case_results[0].block_results["analyze"].results[0]
        assert grading.passed is True
        assert grading.score == pytest.approx(1.0)
        assert grading.assertion_type == "custom:blocked_word"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("stem", "returns", "code", "config", "params", "reason_fragment"),
        [
            (
                "explodes",
                "bool",
                """
                def get_assert(output, context):
                    raise RuntimeError("plugin exploded")
                """,
                {"mode": "strict"},
                None,
                "plugin exploded",
            ),
            (
                "wrong_shape",
                "bool",
                """
                def get_assert(output, context):
                    return {"pass": True, "score": 0.9}
                """,
                {"mode": "strict"},
                None,
                "declares returns: bool",
            ),
            (
                "config_guard",
                "bool",
                """
                def get_assert(output, context):
                    return True
                """,
                {},
                {
                    "type": "object",
                    "properties": {"budget": {"type": "number"}},
                    "required": ["budget"],
                },
                "Config validation failed:",
            ),
            (
                "llm_auth_guard",
                "bool",
                """
                def get_assert(output, context):
                    cfg = context.get("config", {})
                    if not cfg.get("api_key"):
                        raise RuntimeError("401 Unauthorized: OPENAI_API_KEY missing")
                    return True
                """,
                {},
                None,
                "OPENAI_API_KEY missing",
            ),
        ],
    )
    async def test_run_eval_returns_failing_grading_result_for_custom_error_paths(
        self,
        tmp_path: Path,
        stem: str,
        returns: str,
        code: str,
        config: dict[str, Any],
        params: dict[str, Any] | None,
        reason_fragment: str,
    ):
        _write_assertion(
            tmp_path,
            stem=stem,
            returns=returns,
            code=code,
            params=params,
        )
        workflow_path = _write_eval_workflow(
            tmp_path,
            expected_assertions=[{"type": f"custom:{stem}", "config": config}],
        )

        result = await run_eval(str(workflow_path))

        grading = result.case_results[0].block_results["analyze"].results[0]
        assert grading.passed is False
        assert grading.score == pytest.approx(0.0)
        assert reason_fragment in grading.reason
