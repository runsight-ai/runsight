from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from runsight_api.domain.entities.run import RunStatus
from runsight_api.main import app
from runsight_api.transport.deps import get_execution_service, get_run_service


client = TestClient(app, raise_server_exceptions=False)


def teardown_function():
    app.dependency_overrides.clear()


def _child_workflow_input_schema() -> dict[str, dict[str, object]]:
    return {
        "topic": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": False,
        },
        "mode": {
            "type": "string",
            "required": False,
            "default": "summary",
            "description": None,
            "sensitive": False,
        },
        "child_token": {
            "type": "string",
            "required": True,
            "default": None,
            "description": None,
            "sensitive": True,
        },
    }


def _child_workflow_inputs() -> dict[str, dict[str, object]]:
    return {
        "topic": {
            "type": "string",
            "sensitive": False,
            "source": "provided",
            "value": "audit runs",
        },
        "mode": {
            "type": "string",
            "sensitive": False,
            "source": "defaulted",
            "value": "summary",
        },
        "child_token": {
            "type": "string",
            "sensitive": True,
            "source": "provided",
        },
    }


def _mock_run(
    run_id: str = "run_923_child",
    *,
    parent_run_id: str | None = None,
    root_run_id: str | None = None,
    depth: int = 0,
    workflow_id: str = "wf_923",
    workflow_name: str = "run923_inputs",
):
    run = Mock()
    run.id = run_id
    run.workflow_id = workflow_id
    run.workflow_name = workflow_name
    run.status = RunStatus.completed
    run.error = None
    run.started_at = 1711900000.0
    run.completed_at = 1711900010.0
    run.duration_s = 10.0
    run.total_cost_usd = 0.25
    run.total_tokens = 250
    run.created_at = 1711900000.0
    run.branch = "main"
    run.source = "manual"
    run.commit_sha = None
    run.run_number = 1
    run.eval_pass_pct = None
    run.eval_score_avg = None
    run.regression_count = 0
    run.regression_types = []
    run.warnings_json = []
    run.parent_run_id = parent_run_id
    run.root_run_id = root_run_id
    run.depth = depth
    run.workflow_inputs = _child_workflow_inputs()
    run.workflow_input_schema = _child_workflow_input_schema()
    return run


def _mock_run_service(*, runs: list[Mock]):
    run_service = Mock()
    run_service.get_run.return_value = runs[0]
    run_service.list_runs_paginated.return_value = (runs, len(runs))
    run_service.get_node_summary.return_value = {
        "total_cost_usd": 0.25,
        "total_tokens": 250,
        "total": 1,
        "completed": 1,
        "running": 0,
        "pending": 0,
        "failed": 0,
        "eval_score_avg": None,
    }
    run_service.get_node_summaries_batch.return_value = {
        run.id: {
            "total_cost_usd": run.total_cost_usd,
            "total_tokens": run.total_tokens,
            "total": 1,
            "completed": 1,
            "running": 0,
            "pending": 0,
            "failed": 0,
            "eval_score_avg": None,
        }
        for run in runs
    }
    run_service.get_run_regressions.return_value = {"count": 0, "issues": []}
    return run_service


def _assert_snapshot_payload(payload: dict[str, object]) -> None:
    assert payload["workflow_input_schema"] == _child_workflow_input_schema()

    workflow_inputs = payload["workflow_inputs"]
    assert workflow_inputs["topic"]["value"] == "audit runs"
    assert workflow_inputs["topic"]["type"] == "string"
    assert workflow_inputs["topic"]["sensitive"] is False
    assert workflow_inputs["topic"]["source"] == "provided"

    assert workflow_inputs["mode"]["value"] == "summary"
    assert workflow_inputs["mode"]["type"] == "string"
    assert workflow_inputs["mode"]["sensitive"] is False
    assert workflow_inputs["mode"]["source"] == "defaulted"

    assert workflow_inputs["child_token"]["type"] == "string"
    assert workflow_inputs["child_token"]["sensitive"] is True
    assert workflow_inputs["child_token"]["source"] == "provided"
    assert "value" not in workflow_inputs["child_token"]
    assert "redacted" not in workflow_inputs["child_token"]

    assert "redacted" not in payload


class TestRunResponseSnapshotContract:
    def test_run_response_model_exposes_workflow_input_snapshot_fields_and_no_redacted_flag(self):
        from runsight_api.transport.schemas.runs import RunResponse

        fields = RunResponse.model_fields
        assert "workflow_inputs" in fields
        assert "workflow_input_schema" in fields
        assert "redacted" not in fields


class TestRunSnapshotResponses:
    def test_run_detail_and_list_expose_child_input_snapshot_by_child_input_name(self):
        run = _mock_run(
            "run_923_child",
            parent_run_id="run_923_parent",
            root_run_id="run_923_parent",
            depth=1,
        )
        run_service = _mock_run_service(runs=[run])
        execution_service = Mock()
        execution_service.launch_execution = AsyncMock()
        app.dependency_overrides[get_run_service] = lambda: run_service
        app.dependency_overrides[get_execution_service] = lambda: execution_service

        detail_response = client.get("/api/runs/run_923_child")
        list_response = client.get("/api/runs")

        assert detail_response.status_code == 200
        assert list_response.status_code == 200

        _assert_snapshot_payload(detail_response.json())
        _assert_snapshot_payload(list_response.json()["items"][0])
