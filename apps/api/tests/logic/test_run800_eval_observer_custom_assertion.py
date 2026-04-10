"""RUN-800: EvalObserver integration coverage for custom assertions with config."""

from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import runsight_core.assertions.deterministic  # noqa: F401
import yaml
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.discovery import AssertionScanner
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_api.logic.observers.eval_observer import EvalObserver


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


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def run_with_node(db_engine):
    run_id = "run_800_custom_eval"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_custom_eval",
            workflow_name="custom_eval_workflow",
            status=RunStatus.pending,
            task_json="{}",
        )
        node = RunNode(
            id=f"{run_id}:analyze",
            run_id=run_id,
            node_id="analyze",
            block_type="LinearBlock",
            status="completed",
            cost_usd=0.02,
            tokens={"total": 128},
            output="calm response",
        )
        session.add(run)
        session.add(node)
        session.commit()
    return db_engine, run_id


@pytest.fixture
def sse_queue():
    return asyncio.Queue()


@pytest.fixture
def sample_soul():
    return Soul(
        id="analyst_v1",
        role="Analyst",
        system_prompt="You are calm and precise.",
        model_name="gpt-4o",
    )


@pytest.fixture
def sample_state():
    return WorkflowState(
        total_cost_usd=0.02,
        total_tokens=128,
        results={"analyze": BlockResult(output="calm response")},
    )


def _register_custom_assertions(base_dir: Path):
    from runsight_core.assertions.registry import register_custom_assertions

    register_custom_assertions(AssertionScanner(base_dir).scan())


class TestEvalObserverCustomAssertions:
    def test_eval_observer_persists_promptfoo_custom_assertion_and_emits_sse(
        self,
        tmp_path: Path,
        run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
    ):
        _write_assertion(
            tmp_path,
            stem="tone_check",
            returns="grading_result",
            code="""
            def get_assert(output, context):
                cfg = context.get("config", {})
                return {
                    "pass": output.startswith(cfg.get("prefix", "")),
                    "score": 0.9,
                    "reason": f"prefix={cfg.get('prefix', '')}",
                }
            """,
        )
        _register_custom_assertions(tmp_path)
        engine, run_id = run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={
                "analyze": [{"type": "custom:tone_check", "config": {"prefix": "calm"}}]
            },
        )

        obs.on_block_complete(
            "custom_eval_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_passed is True
            assert node.eval_score == pytest.approx(0.9)
            assert node.eval_results["assertions"][0]["type"] == "custom:tone_check"
            assert node.eval_results["assertions"][0]["passed"] is True
            assert node.eval_results["assertions"][0]["score"] == pytest.approx(0.9)

        event = sse_queue.get_nowait()
        assert event["event"] == "node_eval_complete"
        assert event["data"]["node_id"] == "analyze"
        assert event["data"]["passed"] is True
        assert event["data"]["assertions"][0]["type"] == "custom:tone_check"
        assert event["data"]["assertions"][0]["score"] == pytest.approx(0.9)

    def test_eval_observer_supports_negated_custom_assertions_with_builtin_regression(
        self,
        tmp_path: Path,
        run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
    ):
        _write_assertion(
            tmp_path,
            stem="blocked_word",
            returns="bool",
            code="""
            def get_assert(output, context):
                return context.get("config", {}).get("blocked") in output
            """,
        )
        _register_custom_assertions(tmp_path)
        engine, run_id = run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={
                "analyze": [
                    {"type": "not-custom:blocked_word", "config": {"blocked": "storm"}},
                    {"type": "contains", "value": "calm"},
                ]
            },
        )

        obs.on_block_complete(
            "custom_eval_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_passed is True
            assert node.eval_score == pytest.approx(1.0)
            assert len(node.eval_results["assertions"]) == 2
            assert node.eval_results["assertions"][0]["type"] == "custom:blocked_word"
            assert node.eval_results["assertions"][1]["passed"] is True

        event = sse_queue.get_nowait()
        assert event["data"]["passed"] is True
        assert len(event["data"]["assertions"]) == 2

    def test_eval_observer_persists_invalid_config_failure_and_emits_sse(
        self,
        tmp_path: Path,
        run_with_node,
        sse_queue,
        sample_state,
        sample_soul,
    ):
        _write_assertion(
            tmp_path,
            stem="budget_guard",
            returns="bool",
            code="""
            def get_assert(output, context):
                return True
            """,
            params={
                "type": "object",
                "properties": {"budget": {"type": "number"}},
                "required": ["budget"],
            },
        )
        _register_custom_assertions(tmp_path)
        engine, run_id = run_with_node
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={"analyze": [{"type": "custom:budget_guard", "config": {}}]},
        )

        obs.on_block_complete(
            "custom_eval_workflow", "analyze", "LinearBlock", 1.0, sample_state, soul=sample_soul
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node.eval_passed is False
            assert node.eval_score == pytest.approx(0.0)
            assert node.eval_results["assertions"][0]["type"] == "custom:budget_guard"
            assert node.eval_results["assertions"][0]["reason"].startswith(
                "Config validation failed:"
            )

        event = sse_queue.get_nowait()
        assert event["data"]["passed"] is False
        assert event["data"]["assertions"][0]["reason"].startswith("Config validation failed:")
