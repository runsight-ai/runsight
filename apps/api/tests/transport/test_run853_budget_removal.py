"""Red tests for RUN-853: Remove budget facade from settings router.

The list_budgets endpoint is a dead facade that returns hardcoded empty data.
These tests verify it has been removed — they should FAIL before Green.
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


def test_budget_api_methods_removed_from_frontend():
    """settings.ts must not contain budget API methods after removal.

    This test uses file inspection to assert that the frontend settings API
    does not export getBudgets, createBudget, updateBudget, or deleteBudget.
    """
    import re
    from pathlib import Path

    settings_ts = Path(__file__).parents[4] / "apps" / "gui" / "src" / "api" / "settings.ts"
    source = settings_ts.read_text(encoding="utf-8")

    budget_methods = ["getBudgets", "createBudget", "updateBudget", "deleteBudget"]
    found = [m for m in budget_methods if re.search(rf"\b{m}\b", source)]

    assert not found, (
        f"Budget API methods still present in apps/gui/src/api/settings.ts: {found}. "
        "Remove getBudgets, createBudget, updateBudget, and deleteBudget."
    )
