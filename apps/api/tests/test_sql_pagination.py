"""
RUN-252: SQL pagination and batch node summaries for GET /runs.

These tests verify that:
- RunRepository uses SQL LIMIT/OFFSET (not Python slicing)
- RunService has a batch method for node summaries (no N+1)
- The runs router delegates pagination to the DB layer
- Default limit is 20, max limit is 100 (clamped server-side)
"""

import ast
import inspect
import textwrap

from fastapi.testclient import TestClient
from unittest.mock import Mock

from runsight_api.main import app
from runsight_api.transport.deps import get_run_service
from runsight_api.data.repositories.run_repo import RunRepository
from runsight_api.logic.services.run_service import RunService
from runsight_api.transport.routers.runs import list_runs


# ---------------------------------------------------------------------------
# 1. RunRepository has a list_runs_paginated method with offset + limit args
# ---------------------------------------------------------------------------


def test_run_repo_has_list_runs_paginated_method():
    """RunRepository must expose a list_runs_paginated method."""
    assert hasattr(RunRepository, "list_runs_paginated"), (
        "RunRepository is missing list_runs_paginated method"
    )
    assert callable(getattr(RunRepository, "list_runs_paginated")), (
        "list_runs_paginated must be callable"
    )


def test_run_repo_list_runs_paginated_accepts_offset_and_limit():
    """list_runs_paginated must accept offset and limit parameters."""
    sig = inspect.signature(RunRepository.list_runs_paginated)
    params = list(sig.parameters.keys())
    assert "offset" in params, "list_runs_paginated must accept an 'offset' parameter"
    assert "limit" in params, "list_runs_paginated must accept a 'limit' parameter"


def test_run_repo_list_runs_paginated_uses_sql_limit_offset():
    """list_runs_paginated source must contain SQL LIMIT and OFFSET, not Python slicing."""
    source = inspect.getsource(RunRepository.list_runs_paginated)
    # Should use SQLModel .offset() and .limit() calls
    assert ".offset(" in source, "list_runs_paginated must use .offset() for SQL pagination"
    assert ".limit(" in source, "list_runs_paginated must use .limit() for SQL pagination"
    # Must NOT use Python list slicing
    assert "[" not in source or "offset:" not in source, (
        "list_runs_paginated must not use Python list slicing"
    )


def test_run_repo_list_runs_paginated_returns_total_count():
    """list_runs_paginated must return a total count alongside the items."""
    source = inspect.getsource(RunRepository.list_runs_paginated)
    # Should use func.count or COUNT to get total
    assert "count" in source.lower(), (
        "list_runs_paginated must include a count query for total records"
    )


# ---------------------------------------------------------------------------
# 2. RunService has a batch method for node summaries
# ---------------------------------------------------------------------------


def test_run_service_has_get_node_summaries_batch_method():
    """RunService must expose a get_node_summaries_batch method."""
    assert hasattr(RunService, "get_node_summaries_batch"), (
        "RunService is missing get_node_summaries_batch method"
    )
    assert callable(getattr(RunService, "get_node_summaries_batch")), (
        "get_node_summaries_batch must be callable"
    )


def test_run_service_get_node_summaries_batch_accepts_run_ids():
    """get_node_summaries_batch must accept a list of run_ids."""
    sig = inspect.signature(RunService.get_node_summaries_batch)
    params = list(sig.parameters.keys())
    assert "run_ids" in params, "get_node_summaries_batch must accept a 'run_ids' parameter"


# ---------------------------------------------------------------------------
# 3. Router does NOT use Python list slicing for pagination
# ---------------------------------------------------------------------------


def test_router_list_runs_does_not_use_python_slicing():
    """The list_runs router must NOT use Python list slicing (e.g., runs[offset:offset+limit])."""
    source = inspect.getsource(list_runs)
    tree = ast.parse(textwrap.dedent(source))
    slices = [node for node in ast.walk(tree) if isinstance(node, ast.Slice)]
    assert len(slices) == 0, (
        "list_runs router must not use Python list slicing — "
        "pagination should be delegated to the database"
    )


def test_router_list_runs_does_not_call_get_node_summary_per_run():
    """The list_runs router must NOT call get_node_summary in a loop (N+1 pattern)."""
    source = inspect.getsource(list_runs)
    assert "get_node_summary(" not in source, (
        "list_runs router must not call get_node_summary per-run — "
        "use get_node_summaries_batch instead"
    )


def test_router_list_runs_calls_batch_summaries():
    """The list_runs router must call get_node_summaries_batch for batch loading."""
    source = inspect.getsource(list_runs)
    assert "get_node_summaries_batch" in source, (
        "list_runs router must call get_node_summaries_batch"
    )


# ---------------------------------------------------------------------------
# 4. Default limit is 20, max limit is clamped to 100
# ---------------------------------------------------------------------------


def test_list_runs_default_limit_is_20():
    """The list_runs endpoint must default limit to 20."""
    sig = inspect.signature(list_runs)
    limit_param = sig.parameters.get("limit")
    assert limit_param is not None, "list_runs must have a 'limit' parameter"
    assert limit_param.default == 20, (
        f"list_runs default limit must be 20, got {limit_param.default}"
    )


def test_list_runs_clamps_limit_to_max_100():
    """Requesting limit > 100 must be clamped to 100 server-side."""
    mock_service = Mock()
    mock_service.list_runs_paginated.return_value = ([], 0)
    mock_service.get_node_summaries_batch.return_value = {}
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        client = TestClient(app)
        client.get("/api/runs?offset=0&limit=999")

        # Verify the service was called with limit clamped to 100
        mock_service.list_runs_paginated.assert_called_once()
        call_args = mock_service.list_runs_paginated.call_args
        _, kwargs = call_args if call_args.kwargs else (call_args[0], {})
        # Check both positional and keyword argument forms
        if kwargs and "limit" in kwargs:
            actual_limit = kwargs["limit"]
        else:
            # positional: list_runs_paginated(offset, limit)
            actual_limit = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("limit")
        assert actual_limit <= 100, (
            f"limit must be clamped to 100, but service received {actual_limit}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Response includes total count from DB (not len of full list)
# ---------------------------------------------------------------------------


def test_list_runs_response_includes_total_from_db():
    """Response total must come from DB count, not len() of all fetched runs."""
    mock_service = Mock()
    # Simulate: DB has 50 runs total, but we only fetch page of 20
    mock_service.list_runs_paginated.return_value = (
        [_make_mock_run(f"run_{i}") for i in range(20)],
        50,
    )
    mock_service.get_node_summaries_batch.return_value = {
        f"run_{i}": {
            "total": 0,
            "completed": 0,
            "running": 0,
            "pending": 0,
            "failed": 0,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        }
        for i in range(20)
    }
    app.dependency_overrides[get_run_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get("/api/runs?offset=0&limit=20")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50, f"total must reflect DB count (50), got {data['total']}"
        assert len(data["items"]) == 20, (
            f"items must contain only the page of 20, got {len(data['items'])}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_mock_run(run_id="run_123"):
    from runsight_api.domain.entities.run import RunStatus

    mock_run = Mock()
    mock_run.id = run_id
    mock_run.workflow_id = "wf_1"
    mock_run.workflow_name = "wf_1"
    mock_run.status = RunStatus.pending
    mock_run.started_at = None
    mock_run.completed_at = None
    mock_run.duration_s = None
    mock_run.total_cost_usd = 0.0
    mock_run.total_tokens = 0
    mock_run.created_at = 123.0
    return mock_run
