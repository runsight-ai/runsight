"""GET /api/models/providers reports provider summary configuration state."""

from fastapi.testclient import TestClient
from unittest.mock import Mock

from runsight_api.main import app
from runsight_api.transport.deps import get_model_service
from tests.transport.model_catalog_helpers import (
    _make_provider_summary,
    _override_model_service,
)

client = TestClient(app)


class TestGetProvidersEndpoint:
    """Tests for GET /api/models/providers route existence and shape."""

    def test_endpoint_exists(self):
        """GET /api/models/providers must return 200, not 404/405."""
        _override_model_service(providers=[])
        try:
            response = client.get("/api/models/providers")
            assert response.status_code != 404, "Route /api/models/providers not registered"
            assert response.status_code != 405
        finally:
            app.dependency_overrides.clear()

    def test_returns_list(self):
        """Response body must be a JSON list (or wrapper with 'items' list)."""
        _override_model_service(providers=[])
        try:
            response = client.get("/api/models/providers")
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            assert isinstance(items, list)
        finally:
            app.dependency_overrides.clear()

    def test_provider_summary_shape(self):
        """Each item must include required ProviderSummary fields."""
        mock_service = Mock()
        mock_service.get_provider_summary.return_value = [_make_provider_summary()]
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models/providers")
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            assert len(items) == 1
            first = items[0]
            required_fields = {"id", "name", "model_count", "is_configured"}
            missing = required_fields - set(first.keys())
            assert not missing, f"ProviderSummary missing fields: {missing}"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# GET /api/models/providers — is_configured flag
# ===========================================================================


class TestProviderConfiguredFlag:
    """Tests verifying the is_configured flag logic."""

    def test_unconfigured_provider_is_false(self):
        """A catalog provider with no matching configured provider must have is_configured=False."""
        _override_model_service(
            providers=[
                _make_provider_summary(id="openai", is_configured=False),
                _make_provider_summary(id="anthropic", is_configured=False),
            ]
        )
        try:
            response = client.get("/api/models/providers")
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["is_configured"] is False
        finally:
            app.dependency_overrides.clear()

    def test_configured_provider_is_true(self):
        """A catalog provider that IS configured must have is_configured=True.

        This test uses a dependency override to inject a configured provider
        and assert the flag flips to True.
        """
        mock_service = Mock()
        mock_service.get_provider_summary.return_value = [
            _make_provider_summary(id="openai", is_configured=True),
            _make_provider_summary(id="anthropic", is_configured=False),
        ]
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models/providers")
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            openai_entry = next((p for p in items if p["id"] == "openai"), None)
            assert openai_entry is not None
            assert openai_entry["is_configured"] is True
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# ModelService unit tests
# ===========================================================================
