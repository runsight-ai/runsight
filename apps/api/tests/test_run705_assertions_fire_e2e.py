"""E2E tests for RUN-705: assertions fire during block execution and produce pass/fail signal.

Every existing assertion test is structural — parsing, config building, or isolated observer
unit tests. These tests exercise the FULL execution pipeline:

    ExecutionService._run_workflow  ->  CompositeObserver  ->  EvalObserver.on_block_complete
        -> _run_assertions_sync  ->  write eval_passed / eval_score / eval_results to DB

The LLM is mocked via LiteLLMClient.achat so no real API calls are made.
"""

import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus


# ---------------------------------------------------------------------------
# YAML workflow definitions
# ---------------------------------------------------------------------------

YAML_CONTAINS_ASSERTION = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: contains
        value: "X"
workflow:
  name: contains_assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

YAML_COST_ASSERTION = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: cost
        threshold: 0.05
workflow:
  name: cost_assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

SOUL_YAML = """\
id: analyst
role: Analyst
system_prompt: You are a careful analyst.
provider: openai
model_name: gpt-4o
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_soul_file(base_dir: Path, name: str, content: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(dedent(content), encoding="utf-8")


def _parse_workflow(yaml_content: str) -> object:
    """Parse a workflow YAML string using a temp directory with the analyst soul."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_soul_file(base, "analyst", SOUL_YAML)
        workflow_file = base / "workflow.yaml"
        workflow_file.write_text(yaml_content, encoding="utf-8")
        return parse_workflow_yaml(str(workflow_file))


def _seed_run(engine, run_id: str, workflow_name: str) -> None:
    """Insert a Run record into the DB for the test."""
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_test",
                workflow_name=workflow_name,
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()


def _make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
    """Build a dict matching LiteLLMClient.achat return shape."""
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# AC1 — contains assertion passes when LLM output includes target string
# ---------------------------------------------------------------------------


class TestContainsAssertionPasses:
    """Block with assertions: [{type: contains, value: "X"}], LLM returns "X"."""

    @pytest.mark.asyncio
    async def test_eval_passed_is_true_in_db(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_contains_pass"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("The answer is X, confirmed."),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode should exist after execution"
            assert node.eval_passed is True, "Assertion should pass when output contains 'X'"
            assert node.eval_score == 1.0, "Score should be 1.0 for a passing contains assertion"

    @pytest.mark.asyncio
    async def test_eval_results_contain_assertion_details(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_contains_pass_details"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("Result X found"),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_results is not None, "eval_results should be populated"
            assertions_list = node.eval_results.get("assertions")
            assert assertions_list is not None, "eval_results should contain 'assertions' key"
            assert len(assertions_list) == 1
            assert assertions_list[0]["passed"] is True
            assert assertions_list[0]["score"] == 1.0


# ---------------------------------------------------------------------------
# AC2 — contains assertion fails when LLM output does NOT include target
# ---------------------------------------------------------------------------


class TestContainsAssertionFails:
    """Same block, LLM returns "Y" (no "X"), assertion fails."""

    @pytest.mark.asyncio
    async def test_eval_passed_is_false_in_db(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_contains_fail"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("The answer is Y, confirmed."),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode should exist after execution"
            assert node.eval_passed is False, "Assertion should fail when output lacks 'X'"

    @pytest.mark.asyncio
    async def test_eval_score_is_zero_on_failure(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_contains_fail_score"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("No match here, just Y."),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_score == 0.0, "Score should be 0.0 for a failing contains assertion"

    @pytest.mark.asyncio
    async def test_eval_results_record_failure_details(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_contains_fail_details"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("Only Y is here."),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_results is not None
            assertions_list = node.eval_results["assertions"]
            assert len(assertions_list) == 1
            assert assertions_list[0]["passed"] is False
            assert assertions_list[0]["score"] == 0.0


# ---------------------------------------------------------------------------
# AC3 — cost assertion evaluates correctly against known cost_usd
# ---------------------------------------------------------------------------


class TestCostAssertionEvaluation:
    """Block executes with known cost_usd, cost assertion threshold evaluated correctly."""

    @pytest.mark.asyncio
    async def test_cost_below_threshold_passes(self, db_engine):
        """cost_usd=0.01 with threshold=0.05 should pass."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_cost_pass"
        _seed_run(db_engine, run_id, "cost_assertion_test")
        wf = _parse_workflow(YAML_COST_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("result", cost_usd=0.01, total_tokens=200),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode should exist after execution"
            assert node.eval_passed is True, (
                f"Cost assertion should pass when cost ({node.cost_usd}) <= threshold (0.05)"
            )
            assert node.eval_score == 1.0

    @pytest.mark.asyncio
    async def test_cost_above_threshold_fails(self, db_engine):
        """cost_usd=0.10 with threshold=0.05 should fail."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_cost_fail"
        _seed_run(db_engine, run_id, "cost_assertion_test")
        wf = _parse_workflow(YAML_COST_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("result", cost_usd=0.10, total_tokens=500),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode should exist after execution"
            assert node.eval_passed is False, (
                f"Cost assertion should fail when cost ({node.cost_usd}) > threshold (0.05)"
            )
            assert node.eval_score == 0.0

    @pytest.mark.asyncio
    async def test_cost_assertion_result_details(self, db_engine):
        """eval_results should contain cost assertion type and pass/fail details."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_cost_details"
        _seed_run(db_engine, run_id, "cost_assertion_test")
        wf = _parse_workflow(YAML_COST_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("result", cost_usd=0.01, total_tokens=200),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze this"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_results is not None
            assertions_list = node.eval_results["assertions"]
            assert len(assertions_list) == 1
            assert assertions_list[0]["passed"] is True


# ---------------------------------------------------------------------------
# AC4 — assertions fire via EvalObserver during execution, not offline
# ---------------------------------------------------------------------------


class TestAssertionsFireDuringExecution:
    """Assertions fire via EvalObserver during execution, not as a separate offline step."""

    @pytest.mark.asyncio
    async def test_eval_results_written_by_time_run_completes(self, db_engine):
        """After _run_workflow returns, eval_passed must already be set on the RunNode."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_inline_fire"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("X marks the spot"),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Go"})

        # No separate "run eval" step needed — results should already be in DB
        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_passed is not None, (
                "eval_passed must be set after execution completes — "
                "EvalObserver should fire during the run, not as a separate step"
            )
            assert node.eval_score is not None
            assert node.eval_results is not None

    @pytest.mark.asyncio
    async def test_sse_queue_receives_eval_event(self, db_engine):
        """EvalObserver should emit node_eval_complete to the streaming observer's SSE queue."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_705_sse_event"
        _seed_run(db_engine, run_id, "contains_assertion_test")
        wf = _parse_workflow(YAML_CONTAINS_ASSERTION)

        # We need to intercept the observer before unregister cleans it up.
        # Capture the streaming observer's queue during execution.
        captured_events = []
        original_unregister = svc.unregister_observer

        def _capture_then_unregister(rid):
            obs = svc.get_observer(rid)
            if obs:
                while not obs.queue.empty():
                    captured_events.append(obs.queue.get_nowait())
            original_unregister(rid)

        svc.unregister_observer = _capture_then_unregister

        with patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            new_callable=AsyncMock,
            return_value=_make_achat_response("X result"),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze"})

        eval_events = [e for e in captured_events if e.get("event") == "node_eval_complete"]
        assert len(eval_events) >= 1, (
            "EvalObserver should emit at least one node_eval_complete event"
        )
        assert eval_events[0]["data"]["node_id"] == "analyze"
        assert eval_events[0]["data"]["passed"] is True
