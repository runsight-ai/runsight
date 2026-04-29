"""Settings router budget facade removal.

The list_budgets endpoint is a dead facade that returns hardcoded empty data.
These tests verify it has been removed.
"""

from fastapi.testclient import TestClient

from runsight_api.main import app

client = TestClient(app)


def test_list_budgets_endpoint_removed():
    """GET /api/settings/budgets must not return 200 — the endpoint should be gone."""
    response = client.get("/api/settings/budgets")
    assert response.status_code in (404, 405), (
        f"Expected 404 or 405 (endpoint removed), got {response.status_code}. "
        "The list_budgets stub endpoint must be deleted from the settings router."
    )
