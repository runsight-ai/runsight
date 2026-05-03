"""API run provenance response surface coverage."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_api_run_service, get_eval_service, get_run_service


COMMITTED_MAIN_SHA = "934" * 13 + "a"
SECRET_INPUT = "secret-run-934-input"
SECRET_AUTH = "Bearer secret-run-934-auth"
SECRET_IDEMPOTENCY = "idem-secret-run-934"

client = TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def _summary() -> dict[str, Any]:
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


def _run(
    run_id: str,
    *,
    source: str,
    status: RunStatus | str = RunStatus.pending,
    branch: str = "main",
    commit_sha: str | None = None,
    source_correlation_id: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> Mock:
    run = Mock()
    run.id = run_id
    run.workflow_id = "wf_run934"
    run.workflow_name = "API Provenance Workflow"
    run.status = status
    run.error = None
    run.started_at = None
    run.completed_at = None
    run.duration_s = None
    run.total_cost_usd = 0.0
    run.total_tokens = 0
    run.created_at = 1711900934.0
    run.branch = branch
    run.source = source
    run.commit_sha = commit_sha
    run.source_correlation_id = source_correlation_id
    run.source_metadata = source_metadata if source_metadata is not None else {}
    run.run_number = None
    run.eval_pass_pct = None
    run.eval_score_avg = None
    run.regression_count = 0
    run.regression_types = []
    run.warnings_json = []
    run.parent_run_id = None
    run.root_run_id = None
    run.depth = 0
    run.workflow_inputs = None
    run.workflow_input_schema = None
    return run


def _eval_service() -> Mock:
    service = Mock()
    service.get_run_regressions.return_value = {"count": 0, "issues": []}
    return service


def _install_run_service(*runs: Mock) -> Mock:
    service = Mock()
    by_id = {run.id: run for run in runs}
    service.list_runs_paginated.return_value = (list(runs), len(runs))
    service.get_run.side_effect = lambda run_id: by_id.get(run_id)
    service.get_node_summary.return_value = _summary()
    service.get_node_summaries_batch.return_value = {run.id: _summary() for run in runs}
    app.dependency_overrides[get_run_service] = lambda: service
    app.dependency_overrides[get_eval_service] = lambda: _eval_service()
    return service


def test_list_and_detail_responses_expose_api_provenance_without_mislabeling_sources() -> None:
    api_run = _run(
        "run_934_api",
        source="api",
        commit_sha=COMMITTED_MAIN_SHA,
        source_correlation_id="corr-run-934",
        source_metadata={
            "entry_path": "direct_api",
            "request_path": "/api/workflows/wf_run934/runs",
        },
    )
    manual_run = _run("run_934_manual", source="manual")
    simulation_run = _run("run_934_simulation", source="simulation", branch="sim/run-934")
    legacy_unknown_run = _run("run_934_legacy", source="legacy-runner")
    _install_run_service(api_run, manual_run, simulation_run, legacy_unknown_run)

    list_response = client.get("/api/runs")
    detail_response = client.get("/api/runs/run_934_api")

    assert list_response.status_code == 200
    items = {item["id"]: item for item in list_response.json()["items"]}
    assert items["run_934_api"]["source"] == "api"
    assert items["run_934_api"]["commit_sha"] == COMMITTED_MAIN_SHA
    assert items["run_934_api"]["source_correlation_id"] == "corr-run-934"
    assert items["run_934_api"]["source_metadata"] == {
        "entry_path": "direct_api",
        "request_path": "/api/workflows/wf_run934/runs",
    }
    assert items["run_934_manual"]["source"] == "manual"
    assert items["run_934_simulation"]["source"] == "simulation"
    assert items["run_934_legacy"]["source"] == "legacy-runner"
    assert items["run_934_legacy"]["source"] != "api"

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["source"] == "api"
    assert detail["commit_sha"] == COMMITTED_MAIN_SHA
    assert detail["source_correlation_id"] == "corr-run-934"
    assert detail["source_metadata"]["entry_path"] == "direct_api"


def test_old_run_detail_and_list_responses_do_not_leak_unsafe_source_metadata() -> None:
    unsafe_api_run = _run(
        "run_934_unsafe_api",
        source="api",
        commit_sha=COMMITTED_MAIN_SHA,
        source_correlation_id="corr-run-934",
        source_metadata={
            "entry_path": "direct_api",
            "request_path": "/api/workflows/wf_run934/runs",
            "headers": {
                "authorization": SECRET_AUTH,
                "x-api-key": "secret-run-934-api-key",
            },
            "raw_body": {"inputs": {"api_token": SECRET_INPUT}},
            "idempotency_key": SECRET_IDEMPOTENCY,
            "nested": [{"token": "nested-secret-run-934"}],
        },
    )
    _install_run_service(unsafe_api_run)

    list_response = client.get("/api/runs")
    detail_response = client.get("/api/runs/run_934_unsafe_api")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    for response in (list_response, detail_response):
        rendered = response.text
        body = response.json()
        run_payload = body["items"][0] if "items" in body else body
        assert run_payload["source"] == "api"
        assert run_payload["source_metadata"]["entry_path"] == "direct_api"
        assert run_payload["source_metadata"]["request_path"] == "/api/workflows/wf_run934/runs"
        assert "headers" not in run_payload["source_metadata"]
        assert "raw_body" not in run_payload["source_metadata"]
        assert "idempotency_key" not in run_payload["source_metadata"]
        assert SECRET_AUTH not in rendered
        assert SECRET_INPUT not in rendered
        assert SECRET_IDEMPOTENCY not in rendered
        assert "authorization" not in rendered.lower()
        assert "api_token" not in rendered
        assert "nested-secret-run-934" not in rendered


async def _created_run(
    *,
    workflow_id: str,
    inputs: dict[str, Any],
    source_correlation_id: str | None,
    source_metadata: dict[str, Any],
) -> Mock:
    return _run(
        "run_934_direct_api",
        source="api",
        status=RunStatus.running,
        commit_sha=COMMITTED_MAIN_SHA,
        source_correlation_id=source_correlation_id,
        source_metadata=dict(source_metadata),
    )


def test_direct_api_accepted_response_reports_current_nonterminal_status_and_safe_provenance() -> (
    None
):
    service = Mock()
    service.create_direct_api_run.side_effect = _created_run
    app.dependency_overrides[get_api_run_service] = lambda: service

    response = client.post(
        "/api/workflows/wf_run934/runs",
        json={"inputs": {"query": "from api", "api_token": SECRET_INPUT}},
        headers={"x-request-id": "corr-run-934", "authorization": SECRET_AUTH},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "run_934_direct_api"
    assert body["source"] == "api"
    assert body["status"] == "running"
    assert body["status"] not in {"completed", "success", "succeeded"}
    assert body["commit_sha"] == COMMITTED_MAIN_SHA
    assert body["source_correlation_id"] == "corr-run-934"
    assert body["source_metadata"] == {
        "entry_path": "direct_api",
        "request_path": "/api/workflows/wf_run934/runs",
    }
    assert SECRET_INPUT not in response.text
    assert SECRET_AUTH not in response.text
