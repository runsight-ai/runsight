"""Shared helpers for settings router transport tests."""

from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app

client = TestClient(app)


def _mock_provider(*, provider_id: str, name: str, models: list[str]):
    provider = Mock()
    provider.id = provider_id
    provider.kind = "provider"
    provider.name = name
    provider.type = "custom"
    provider.status = "active"
    provider.api_key = "configured-key"
    provider.base_url = None
    provider.models = models
    provider.created_at = None
    provider.updated_at = None
    provider.is_active = True
    return provider


def _assert_provider_test_contract(payload: dict):
    assert payload["success"] in (True, False)
    assert isinstance(payload["message"], str)
    assert isinstance(payload["model_count"], int)
    assert payload["model_count"] >= 0
    assert payload["latency_ms"] >= 0
