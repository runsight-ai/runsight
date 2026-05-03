"""Child-run endpoint returns direct children with warning snapshots."""

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service, get_run_service
from tests.transport.child_run_helpers import (
    _make_mock_run,
    _mock_eval_service,
    _mock_run_service_with_children,
)


class TestGetChildrenEndpointExists:
    """The ``GET /runs/{run_id}/children`` endpoint must exist and return a list."""

    def test_get_children_endpoint_exists(self):
        """GET /runs/{run_id}/children returns 200 with a list response."""
        parent = _make_mock_run("run_parent")
        child = _make_mock_run(
            "run_child",
            parent_run_id="run_parent",
            root_run_id="run_parent",
            depth=1,
        )

        mock_service = _mock_run_service_with_children(parent, [child])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_parent/children")
            assert response.status_code == 200, (
                f"Expected 200 from GET /runs/{{run_id}}/children, got {response.status_code}. "
                "The endpoint must expose the durable child-run list contract."
            )
            body = response.json()
            assert isinstance(body, list), (
                f"Expected a list response from /children, got {type(body).__name__}"
            )
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 2. GET /runs/{run_id}/children returns only child runs
# ===========================================================================


class TestGetChildrenReturnsChildRunsOnly:
    """The children endpoint must return only runs whose parent_run_id matches."""

    def test_get_children_returns_child_runs_only(self):
        """Create parent + child + unrelated. Endpoint returns only the child."""
        parent = _make_mock_run("run_parent")
        child = _make_mock_run(
            "run_child",
            parent_run_id="run_parent",
            root_run_id="run_parent",
            depth=1,
        )
        # The unrelated run should NOT appear — it's not set up on the mock
        # service's list_children return.
        mock_service = _mock_run_service_with_children(parent, [child])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_parent/children")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1, f"Expected exactly 1 child run, got {len(body)}"
            assert body[0]["id"] == "run_child"
            assert body[0]["parent_run_id"] == "run_parent"
            assert body[0]["root_run_id"] == "run_parent"
            assert body[0]["depth"] == 1
            assert body[0]["warnings"] == []
        finally:
            app.dependency_overrides.clear()

    def test_get_children_wires_non_empty_warnings(self):
        """Children response must expose warnings from child.warnings_json when present."""
        parent = _make_mock_run("run_parent")
        child = _make_mock_run(
            "run_child_warned",
            parent_run_id="run_parent",
            root_run_id="run_parent",
            depth=1,
        )
        child.warnings_json = [
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": "fetch_child_profile",
            }
        ]
        mock_service = _mock_run_service_with_children(parent, [child])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_parent/children")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1
            assert body[0]["id"] == "run_child_warned"
            assert body[0]["warnings"] == child.warnings_json
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 3. GET /runs/{run_id}/children returns empty list for leaf runs
# ===========================================================================


class TestGetChildrenEmptyForLeafRun:
    """A run with no children returns an empty list from the children endpoint."""

    def test_get_children_empty_for_leaf_run(self):
        """Leaf run (no children) returns []."""
        leaf = _make_mock_run("run_leaf")
        mock_service = _mock_run_service_with_children(leaf, [])
        mock_eval = _mock_eval_service()

        app.dependency_overrides[get_run_service] = lambda: mock_service
        app.dependency_overrides[get_eval_service] = lambda: mock_eval
        client = TestClient(app, raise_server_exceptions=False)

        try:
            response = client.get("/api/runs/run_leaf/children")
            assert response.status_code == 200
            body = response.json()
            assert body == [], f"Expected empty list for leaf run, got {body}"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 4. GET /runs/{run_id} includes linkage fields in response
# ===========================================================================
