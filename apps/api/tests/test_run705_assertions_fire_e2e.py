"""E2E tests for RUN-705: assertions fire during block execution and produce pass/fail signal.

Every existing assertion test is structural — parsing, config building, or isolated observer
unit tests. These tests exercise the FULL execution pipeline via the HTTP layer:

    HTTP POST /api/runs  ->  RunService.create_run  ->  ExecutionService.launch_execution
        ->  workflow engine  ->  mocked LLM  ->  EvalObserver.on_block_complete
            ->  _run_assertions_sync  ->  write eval_passed / eval_score / eval_results to DB

The LLM is mocked via LiteLLMClient.achat so no real API calls are made.
Results are verified through GET /api/runs/{run_id}/nodes (HTTP layer, not direct DB reads).
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


# ---------------------------------------------------------------------------
# YAML workflow definitions
# ---------------------------------------------------------------------------

YAML_CONTAINS_ASSERTION = """\
id: contains-assertion-workflow
kind: workflow
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
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
id: cost-assertion-workflow
kind: workflow
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    """Create a workflow YAML file at custom/workflows/<workflow_id>.yaml."""
    wf_dir = base_dir / "custom" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    canvas_dir = wf_dir / ".canvas"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


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


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0):
    """Poll DB until the run reaches a terminal status or timeout expires."""
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run and run.status in terminal:
                return run
        await asyncio.sleep(0.1)
    with Session(engine) as session:
        return session.get(Run, run_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Fresh in-memory SQLite engine with all tables."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def base_dir():
    """Temporary directory for workflow YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_workflow_file(base, "contains-assertion-workflow", YAML_CONTAINS_ASSERTION)
        _write_workflow_file(base, "cost-assertion-workflow", YAML_COST_ASSERTION)
        yield base


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    """FastAPI app wired with real services backed by in-memory SQLite and temp filesystem.

    Only LiteLLMClient.achat is mocked externally — everything else is real.
    """
    from fastapi import FastAPI
    from sqlmodel import Session

    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
    )
    from runsight_api.transport.routers import runs

    app = FastAPI()
    app.include_router(runs.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))

    mock_secrets = Mock()
    mock_secrets.resolve = Mock(return_value="sk-fake-test-key-for-e2e")

    execution_service = ExecutionService(
        run_repo=None,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=mock_secrets,
        settings_repo=None,
    )
    app.state.execution_service = execution_service

    def _get_run_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return RunService(run_repo, workflow_repo)

    def _get_execution_service(request=None):
        return execution_service

    def _get_eval_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return EvalService(run_repo)

    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_execution_service] = _get_execution_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider():
    """A mock provider object that satisfies the provider repo list_all call."""
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.api_key = "sk-test"
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


# ---------------------------------------------------------------------------
# AC1 — contains assertion passes when LLM output includes target string
# ---------------------------------------------------------------------------


class TestContainsAssertionPasses:
    """Block with assertions: [{type: contains, value: "X"}], LLM returns "X"."""

    @pytest.mark.asyncio
    async def test_eval_passed_is_true_via_api(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("The answer is X, confirmed."),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None, "RunNode for 'analyze' must exist after execution"
        assert analyze_node["eval_passed"] is True, "Assertion should pass when output contains 'X'"
        assert analyze_node["eval_score"] == 1.0, (
            "Score should be 1.0 for a passing contains assertion"
        )

    @pytest.mark.asyncio
    async def test_eval_results_contain_assertion_details(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("Result X found"),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None
        eval_results = analyze_node.get("eval_results")
        assert eval_results is not None, "eval_results should be populated"
        assertions_list = eval_results.get("assertions")
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
    async def test_eval_passed_is_false_via_api(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("The answer is Y, confirmed."),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None, "RunNode for 'analyze' must exist after execution"
        assert analyze_node["eval_passed"] is False, "Assertion should fail when output lacks 'X'"

    @pytest.mark.asyncio
    async def test_eval_score_is_zero_on_failure(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("No match here, just Y."),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None
        assert analyze_node["eval_score"] == 0.0, (
            "Score should be 0.0 for a failing contains assertion"
        )

    @pytest.mark.asyncio
    async def test_eval_results_record_failure_details(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("Only Y is here."),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None
        eval_results = analyze_node.get("eval_results")
        assert eval_results is not None
        assertions_list = eval_results["assertions"]
        assert len(assertions_list) == 1
        assert assertions_list[0]["passed"] is False
        assert assertions_list[0]["score"] == 0.0


# ---------------------------------------------------------------------------
# AC3 — cost assertion evaluates correctly against known cost_usd
# ---------------------------------------------------------------------------


class TestCostAssertionEvaluation:
    """Block executes with known cost_usd, cost assertion threshold evaluated correctly."""

    @pytest.mark.asyncio
    async def test_cost_below_threshold_passes(
        self, app_with_real_services, db_engine, mock_provider
    ):
        """cost_usd=0.01 with threshold=0.05 should pass."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("result", cost_usd=0.01, total_tokens=200),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "cost-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None, "RunNode for 'analyze' must exist after execution"
        assert analyze_node["eval_passed"] is True, (
            "Cost assertion should pass when cost <= threshold (0.05)"
        )
        assert analyze_node["eval_score"] == 1.0

    @pytest.mark.asyncio
    async def test_cost_above_threshold_fails(
        self, app_with_real_services, db_engine, mock_provider
    ):
        """cost_usd=0.10 with threshold=0.05 should fail."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("result", cost_usd=0.10, total_tokens=500),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "cost-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None, "RunNode for 'analyze' must exist after execution"
        assert analyze_node["eval_passed"] is False, (
            "Cost assertion should fail when cost > threshold (0.05)"
        )
        assert analyze_node["eval_score"] == 0.0

    @pytest.mark.asyncio
    async def test_cost_assertion_result_details(
        self, app_with_real_services, db_engine, mock_provider
    ):
        """eval_results should contain cost assertion type and pass/fail details."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("result", cost_usd=0.01, total_tokens=200),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "cost-assertion-workflow",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None
        eval_results = analyze_node.get("eval_results")
        assert eval_results is not None
        assertions_list = eval_results["assertions"]
        assert len(assertions_list) == 1
        assert assertions_list[0]["passed"] is True


# ---------------------------------------------------------------------------
# AC4 — assertions fire via EvalObserver during execution, not offline
# ---------------------------------------------------------------------------


class TestAssertionsFireDuringExecution:
    """Assertions fire via EvalObserver during execution, not as a separate offline step."""

    @pytest.mark.asyncio
    async def test_eval_results_written_by_time_run_completes(
        self, app_with_real_services, db_engine, mock_provider
    ):
        """After the run completes, eval_passed must already be set on the node — no separate step."""
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("X marks the spot"),
                ),
                patch.object(
                    app_with_real_services.state.execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Go"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            # No separate "run eval" step — results should already be present
            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        nodes = nodes_response.json()
        analyze_node = next((n for n in nodes if n["node_id"] == "analyze"), None)
        assert analyze_node is not None
        assert analyze_node["eval_passed"] is not None, (
            "eval_passed must be set after execution completes — "
            "EvalObserver should fire during the run, not as a separate step"
        )
        assert analyze_node["eval_score"] is not None
        assert analyze_node["eval_results"] is not None

    @pytest.mark.asyncio
    async def test_sse_queue_receives_eval_event(
        self, app_with_real_services, db_engine, mock_provider
    ):
        """EvalObserver should emit node_eval_complete to the streaming observer's SSE queue."""
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service

        # Capture SSE events before unregister cleans up the observer
        captured_events: list = []
        original_unregister = execution_service.unregister_observer

        def _capture_then_unregister(rid):
            obs = execution_service.get_observer(rid)
            if obs:
                while not obs.queue.empty():
                    captured_events.append(obs.queue.get_nowait())
            original_unregister(rid)

        execution_service.unregister_observer = _capture_then_unregister

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("X result"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "contains-assertion-workflow",
                        "task_data": {"instruction": "Analyze"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

        eval_events = [e for e in captured_events if e.get("event") == "node_eval_complete"]
        assert len(eval_events) >= 1, (
            "EvalObserver should emit at least one node_eval_complete event"
        )
        assert eval_events[0]["data"]["node_id"] == "analyze"
        assert eval_events[0]["data"]["passed"] is True
