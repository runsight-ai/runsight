"""Router smoke coverage for /api/runs endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from runsight_core.redaction import RunRedactor

from runsight_api.domain.entities.run import RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_execution_service, get_run_service


client = TestClient(app)
TEST_BRANCH = "sim/test/20260330/abc12"


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


def _summary() -> dict[str, object]:
    return {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "nodes_count": 0,
        "total": 0,
        "completed": 0,
        "running": 0,
        "pending": 0,
        "failed": 0,
    }


def _mock_eval_svc():
    mock_eval = Mock()
    mock_eval.get_run_regressions.return_value = {"count": 0, "issues": []}
    return mock_eval


def _make_mock_run(run_id="run_transport_primary", *, branch: str = TEST_BRANCH):
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_runs_router"
    run.workflow_name = "Runs Router Workflow"
    run.status = RunStatus.pending
    run.started_at = 123.0
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 123.0
    run.source = "manual"
    run.branch = branch
    run.commit_sha = None
    run.run_number = None
    run.eval_pass_pct = None
    run.regression_count = None
    run.parent_run_id = None
    run.root_run_id = None
    run.depth = 0
    run.warnings_json = None
    run.workflow_inputs = {}
    run.workflow_input_schema = {}
    run.error = None
    return run


def test_runs_list_smoke_returns_paginated_response() -> None:
    run = _make_mock_run()
    run.warnings_json = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    run_service = Mock()
    run_service.list_runs_paginated.return_value = ([run], 1)
    run_service.get_node_summaries_batch.return_value = {run.id: _summary()}
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_eval_service] = lambda: _mock_eval_svc()

    response = client.get("/api/runs?limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 5
    assert payload["items"][0]["id"] == run.id
    assert payload["items"][0]["warnings"] == run.warnings_json
    run_service.list_runs_paginated.assert_called_once_with(
        offset=0,
        limit=5,
        status=None,
        workflow_id=None,
        source=None,
        branch=None,
    )


def test_runs_post_smoke_prepares_persists_and_launches() -> None:
    run = _make_mock_run("run_new", branch=TEST_BRANCH)
    run.source = "simulation"
    run_service = Mock()
    run_service.create_run.return_value = run
    run_service.refresh_run.return_value = run
    execution_service = Mock()
    prepared = _prepared_inputs({"instruction": "summarize"})
    execution_service.prepare_run_inputs.return_value = prepared
    execution_service.launch_execution = AsyncMock()
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_execution_service] = lambda: execution_service

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": "wf_runs_router",
            "inputs": {"instruction": "summarize"},
            "branch": TEST_BRANCH,
            "source": "simulation",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "run_new"
    assert response.json()["branch"] == TEST_BRANCH
    assert response.json()["source"] == "simulation"
    execution_service.prepare_run_inputs.assert_called_once_with(
        "wf_runs_router",
        {"instruction": "summarize"},
        branch=TEST_BRANCH,
    )
    run_service.create_run.assert_called_once_with(
        "wf_runs_router",
        prepared,
        branch=TEST_BRANCH,
        source="simulation",
    )
    execution_service.launch_execution.assert_awaited_once_with(
        "run_new",
        "wf_runs_router",
        prepared,
        branch=TEST_BRANCH,
    )


def test_runs_nodes_smoke_serializes_node_payload() -> None:
    node = Mock()
    node.id = "run_transport_primary:analyze"
    node.run_id = "run_transport_primary"
    node.node_id = "analyze"
    node.block_type = "linear"
    node.status = "completed"
    node.started_at = 1.0
    node.completed_at = 2.0
    node.duration_s = 1.0
    node.cost_usd = 0.01
    node.tokens = {"total": 10}
    node.error = None
    node.output = "done"
    node.soul_id = None
    node.model_name = None
    node.eval_score = None
    node.eval_passed = None
    node.eval_results = None
    node.child_run_id = None
    node.exit_handle = None
    run_service = Mock()
    run_service.get_run_nodes.return_value = [node]
    app.dependency_overrides[get_run_service] = lambda: run_service

    response = client.get("/api/runs/run_transport_primary/nodes")

    assert response.status_code == 200
    assert response.json()[0]["node_id"] == "analyze"
    assert response.json()[0]["output"] == "done"
