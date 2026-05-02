"""Shared helpers for model catalog transport tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.transport.deps import get_model_service

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

client = TestClient(app)


def _override_model_service(*, models=None, providers=None):
    mock_service = Mock()
    mock_service.get_available_models.return_value = list(models or [])
    mock_service.get_provider_summary.return_value = list(providers or [])
    app.dependency_overrides[get_model_service] = lambda: mock_service
    return mock_service


def _make_model_response(
    *,
    provider: str = "openai",
    provider_name: str = "Openai",
    model_id: str = "gpt-4o",
    mode: str = "chat",
    max_tokens: int = 4096,
    input_cost_per_token: float = 0.00003,
    output_cost_per_token: float = 0.00006,
    supports_vision: bool = False,
    supports_function_calling: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        provider=provider,
        provider_name=provider_name,
        model_id=model_id,
        mode=mode,
        max_tokens=max_tokens,
        input_cost_per_token=input_cost_per_token,
        output_cost_per_token=output_cost_per_token,
        supports_vision=supports_vision,
        supports_function_calling=supports_function_calling,
    )


def _make_provider_summary(
    *,
    id: str = "openai",
    name: str = "Openai",
    model_count: int = 5,
    is_configured: bool = False,
) -> dict:
    return {
        "id": id,
        "name": name,
        "model_count": model_count,
        "is_configured": is_configured,
    }


# ===========================================================================
# GET /api/models — basic wiring
# ===========================================================================
