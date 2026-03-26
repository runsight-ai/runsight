"""
RED-TEAM tests for RUN-341: A6 — Attention section — end-to-end.

These tests verify the new GET /api/dashboard/attention endpoint that queries
RunNodes with eval deltas and generates typed attention items:

  1. Endpoint exists and returns 200
  2. Returns empty list when no attention items
  3. Returns assertion_regression items (eval_passed=false where previous run had true)
  4. Returns cost_spike items (delta.cost_pct > 20 after prompt change)
  5. Returns quality_drop items (delta.score_delta < -0.1)
  6. Returns new_baseline items (delta = null, informational)
  7. Respects ?limit= query param
  8. Response conforms to AttentionItemsResponse Pydantic model

Expected: ALL tests fail — the endpoint does not exist yet.
"""

import time

from fastapi.testclient import TestClient
from unittest.mock import Mock

from runsight_api.main import app
from runsight_api.transport.deps import get_eval_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_node(
    *,
    node_id: str = "analyze",
    run_id: str = "run_001",
    soul_id: str = "researcher_v1",
    soul_version: str = "sha256:abc",
    eval_score: float | None = 0.95,
    eval_passed: bool | None = True,
    cost_usd: float = 0.005,
    tokens: dict | None = None,
    eval_results: dict | None = None,
) -> Mock:
    """Create a mock RunNode with eval fields populated."""
    m = Mock()
    m.node_id = node_id
    m.run_id = run_id
    m.soul_id = soul_id
    m.soul_version = soul_version
    m.eval_score = eval_score
    m.eval_passed = eval_passed
    m.cost_usd = cost_usd
    m.tokens = tokens or {"prompt": 100, "completion": 50, "total": 150}
    m.eval_results = eval_results
    m.created_at = time.time()
    return m


# ===========================================================================
# 1. Endpoint registration and basic shape
# ===========================================================================


class TestAttentionEndpointExists:
    """GET /api/dashboard/attention must be a registered route."""

    def test_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/api/dashboard/attention" in routes

    def test_returns_200(self):
        """Endpoint returns 200 even when no items exist."""
        mock_service = Mock()
        mock_service.get_attention_items.return_value = []
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_response_has_items_list(self):
        """Response body must contain an 'items' list."""
        mock_service = Mock()
        mock_service.get_attention_items.return_value = []
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

        app.dependency_overrides.clear()


# ===========================================================================
# 2. Empty list when no attention items
# ===========================================================================


class TestAttentionEmptyList:
    """Returns empty items when no attention-worthy conditions exist."""

    def setup_method(self):
        self.mock_service = Mock()
        self.mock_service.get_attention_items.return_value = []
        app.dependency_overrides[get_eval_service] = lambda: self.mock_service

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_empty_items(self):
        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert data["items"] == []

    def test_items_count_is_zero(self):
        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert len(data["items"]) == 0


# ===========================================================================
# 3. Assertion regression items
# ===========================================================================


class TestAssertionRegressionItems:
    """Items of type assertion_regression when eval_passed=false but previous was true."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_assertion_regression_type(self):
        """A node that previously passed but now fails generates an assertion_regression item."""
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="assertion_regression",
                title="Assertion 'contains Sources' failed",
                description="Workflow 'Research Agent' — run run_002",
                run_id="run_002",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert len(data["items"]) >= 1
        item = data["items"][0]
        assert item["type"] == "assertion_regression"

    def test_assertion_regression_has_title(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="assertion_regression",
                title="Assertion 'contains Sources' failed",
                description="Workflow 'Research Agent' — run run_002",
                run_id="run_002",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        item = response.json()["items"][0]
        assert "title" in item
        assert len(item["title"]) > 0

    def test_assertion_regression_has_run_id_and_workflow_id(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="assertion_regression",
                title="Assertion 'contains Sources' failed",
                description="Workflow 'Research Agent' — run run_002",
                run_id="run_002",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        item = response.json()["items"][0]
        assert "run_id" in item
        assert "workflow_id" in item


# ===========================================================================
# 4. Cost spike items
# ===========================================================================


class TestCostSpikeItems:
    """Items of type cost_spike when delta.cost_pct > 20."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_cost_spike_type(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="cost_spike",
                title="Cost +34% after prompt change",
                description="Soul 'researcher_v1' — workflow 'Research Agent'",
                run_id="run_003",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert any(item["type"] == "cost_spike" for item in data["items"])

    def test_cost_spike_title_contains_percentage(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="cost_spike",
                title="Cost +34% after prompt change",
                description="Soul 'researcher_v1'",
                run_id="run_003",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        item = next(i for i in response.json()["items"] if i["type"] == "cost_spike")
        assert "%" in item["title"]


# ===========================================================================
# 5. Quality drop items
# ===========================================================================


class TestQualityDropItems:
    """Items of type quality_drop when delta.score_delta < -0.1."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_quality_drop_type(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="quality_drop",
                title="Quality score dropped 0.15",
                description="Soul 'researcher_v1' — workflow 'Research Agent'",
                run_id="run_004",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert any(item["type"] == "quality_drop" for item in data["items"])

    def test_quality_drop_severity_is_warning(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="quality_drop",
                title="Quality score dropped 0.15",
                description="Soul 'researcher_v1'",
                run_id="run_004",
                workflow_id="wf_research",
                severity="warning",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        item = next(i for i in response.json()["items"] if i["type"] == "quality_drop")
        assert item["severity"] == "warning"


# ===========================================================================
# 6. New baseline items (informational, not warning)
# ===========================================================================


class TestNewBaselineItems:
    """Items of type new_baseline when delta is null — informational, not warning."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_returns_new_baseline_type(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="new_baseline",
                title="New prompt version detected",
                description="Soul 'researcher_v1' — first run of version sha256:xyz",
                run_id="run_005",
                workflow_id="wf_research",
                severity="info",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert any(item["type"] == "new_baseline" for item in data["items"])

    def test_new_baseline_severity_is_info_not_warning(self):
        """new_baseline items must have severity 'info', not 'warning'."""
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        mock_service.get_attention_items.return_value = [
            AttentionItem(
                type="new_baseline",
                title="New prompt version detected",
                description="Soul 'researcher_v1'",
                run_id="run_005",
                workflow_id="wf_research",
                severity="info",
            )
        ]
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        item = next(i for i in response.json()["items"] if i["type"] == "new_baseline")
        assert item["severity"] == "info"
        assert item["severity"] != "warning"


# ===========================================================================
# 7. Limit query parameter
# ===========================================================================


class TestAttentionLimitParam:
    """GET /api/dashboard/attention?limit=N respects the limit."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_limit_defaults_to_5(self):
        """When no limit param, at most 5 items are returned."""
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        items = [
            AttentionItem(
                type="cost_spike",
                title=f"Cost spike #{i}",
                description=f"Item {i}",
                run_id=f"run_{i:03d}",
                workflow_id="wf_1",
                severity="warning",
            )
            for i in range(10)
        ]
        mock_service.get_attention_items.return_value = items
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention")
        data = response.json()
        assert len(data["items"]) <= 5

    def test_limit_param_respected(self):
        """?limit=3 returns at most 3 items."""
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        items = [
            AttentionItem(
                type="cost_spike",
                title=f"Cost spike #{i}",
                description=f"Item {i}",
                run_id=f"run_{i:03d}",
                workflow_id="wf_1",
                severity="warning",
            )
            for i in range(10)
        ]
        mock_service.get_attention_items.return_value = items
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention?limit=3")
        data = response.json()
        assert len(data["items"]) <= 3

    def test_limit_param_of_1_returns_single_item(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        mock_service = Mock()
        items = [
            AttentionItem(
                type="assertion_regression",
                title="Regression",
                description="Desc",
                run_id=f"run_{i:03d}",
                workflow_id="wf_1",
                severity="warning",
            )
            for i in range(5)
        ]
        mock_service.get_attention_items.return_value = items
        app.dependency_overrides[get_eval_service] = lambda: mock_service

        response = client.get("/api/dashboard/attention?limit=1")
        data = response.json()
        assert len(data["items"]) == 1


# ===========================================================================
# 8. Pydantic response model shape
# ===========================================================================


class TestAttentionResponseModel:
    """The AttentionItem and AttentionItemsResponse Pydantic models must exist."""

    def test_attention_item_importable(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        assert AttentionItem is not None

    def test_attention_items_response_importable(self):
        from runsight_api.transport.schemas.dashboard import AttentionItemsResponse

        assert AttentionItemsResponse is not None

    def test_attention_item_has_type_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "type" in fields

    def test_attention_item_has_title_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "title" in fields

    def test_attention_item_has_description_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "description" in fields

    def test_attention_item_has_run_id_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "run_id" in fields

    def test_attention_item_has_workflow_id_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "workflow_id" in fields

    def test_attention_item_has_severity_field(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        fields = AttentionItem.model_fields
        assert "severity" in fields

    def test_attention_items_response_has_items_list(self):
        from runsight_api.transport.schemas.dashboard import AttentionItemsResponse

        fields = AttentionItemsResponse.model_fields
        assert "items" in fields

    def test_attention_item_type_enum_values(self):
        """type field must accept the four attention types."""
        from runsight_api.transport.schemas.dashboard import AttentionItem

        for attention_type in [
            "assertion_regression",
            "cost_spike",
            "quality_drop",
            "new_baseline",
        ]:
            item = AttentionItem(
                type=attention_type,
                title="Test",
                description="Test description",
                run_id="run_001",
                workflow_id="wf_001",
                severity="warning" if attention_type != "new_baseline" else "info",
            )
            assert item.type == attention_type

    def test_attention_item_serializes_to_json(self):
        from runsight_api.transport.schemas.dashboard import AttentionItem

        item = AttentionItem(
            type="assertion_regression",
            title="Assertion 'contains Sources' failed",
            description="Workflow 'Research Agent' — run run_002",
            run_id="run_002",
            workflow_id="wf_research",
            severity="warning",
        )
        data = item.model_dump(mode="json")
        assert data["type"] == "assertion_regression"
        assert data["run_id"] == "run_002"
        assert data["severity"] == "warning"

    def test_attention_items_response_serializes_to_json(self):
        from runsight_api.transport.schemas.dashboard import (
            AttentionItem,
            AttentionItemsResponse,
        )

        items = [
            AttentionItem(
                type="cost_spike",
                title="Cost +34%",
                description="Desc",
                run_id="run_003",
                workflow_id="wf_1",
                severity="warning",
            )
        ]
        resp = AttentionItemsResponse(items=items)
        data = resp.model_dump(mode="json")
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "cost_spike"
