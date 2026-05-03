"""Model catalog dependency and response schemas are importable."""


class TestDependencyWiring:
    """Verify the DI function for ModelService exists in deps.py."""

    def test_get_model_service_importable(self):
        from runsight_api.transport.deps import get_model_service  # noqa: F401

    def test_get_model_catalog_importable(self):
        from runsight_api.transport.deps import get_model_catalog  # noqa: F401


# ===========================================================================
# Response schema (Pydantic models)
# ===========================================================================


class TestResponseSchemas:
    """Verify ModelResponse and ProviderSummary Pydantic schemas exist."""

    def test_model_response_importable(self):
        from runsight_api.transport.routers.models import ModelResponse  # noqa: F401

    def test_provider_summary_importable(self):
        from runsight_api.transport.routers.models import ProviderSummary  # noqa: F401

    def test_model_response_has_required_fields(self):
        from runsight_api.transport.routers.models import ModelResponse

        fields = set(ModelResponse.model_fields.keys())
        expected = {
            "provider",
            "provider_name",
            "model_id",
            "mode",
            "max_tokens",
            "input_cost_per_token",
            "output_cost_per_token",
            "supports_vision",
            "supports_function_calling",
        }
        missing = expected - fields
        assert not missing, f"ModelResponse missing fields: {missing}"

    def test_provider_summary_has_required_fields(self):
        from runsight_api.transport.routers.models import ProviderSummary

        fields = set(ProviderSummary.model_fields.keys())
        expected = {"id", "name", "model_count", "is_configured"}
        missing = expected - fields
        assert not missing, f"ProviderSummary missing fields: {missing}"
