"""Domain and transport node-summary schemas stay aligned."""

from fastapi.testclient import TestClient

from runsight_api.domain.value_objects import NodeSummary as DomainNodeSummary
from runsight_api.main import app
from runsight_api.transport.schemas.runs import NodeSummary as TransportNodeSummary

client = TestClient(app)


class TestNodeSummarySchemaAlignment:
    """The domain NodeSummary should match the transport schema exactly: 5 fields."""

    def test_domain_node_summary_has_no_killed_field(self):
        """domain/value_objects.py NodeSummary should not have a 'killed' field."""
        fields = set(DomainNodeSummary.model_fields.keys())
        assert "killed" not in fields, (
            f"NodeSummary in domain/value_objects.py still has 'killed' field. Fields: {fields}"
        )

    def test_domain_node_summary_has_exactly_five_fields(self):
        """Domain NodeSummary should have exactly: total, completed, running, pending, failed."""
        expected = {"total", "completed", "running", "pending", "failed"}
        actual = set(DomainNodeSummary.model_fields.keys())
        assert actual == expected, (
            f"Domain NodeSummary fields mismatch. Expected {expected}, got {actual}"
        )

    def test_domain_and_transport_schemas_match(self):
        """Domain and transport NodeSummary should have the same field set."""
        domain_fields = set(DomainNodeSummary.model_fields.keys())
        transport_fields = set(TransportNodeSummary.model_fields.keys())
        assert domain_fields == transport_fields, (
            f"Schema mismatch: domain={domain_fields}, transport={transport_fields}"
        )


# ---------------------------------------------------------------------------
# 2. RunService.get_node_summary returns per-status breakdown
# ---------------------------------------------------------------------------
