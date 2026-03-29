"""Red tests for RUN-150: Core ModelCatalogPort Protocol + LiteLLMModelCatalog.

Tests cover:
- ModelInfo and ProviderInfo dataclass creation + frozen enforcement
- ModelCatalogPort protocol structural subtyping check
- LiteLLMModelCatalog loading from litellm.model_cost
- Filtering by provider, mode, capabilities
- get_model_info() lookup and miss
- Graceful handling of missing fields, empty catalog, unavailable litellm
- Import boundary: litellm must not leak outside LiteLLMModelCatalog

All tests should FAIL until the implementation exists.
"""

import dataclasses
import sys
import types
from typing import Protocol
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Import targets (will fail until implementation exists)
# ---------------------------------------------------------------------------

from runsight_core.llm.model_catalog import (
    LiteLLMModelCatalog,
    ModelCatalogPort,
    ModelInfo,
    ProviderInfo,
)


# ===========================================================================
# 1. ModelInfo dataclass
# ===========================================================================


class TestModelInfoDataclass:
    """ModelInfo is a frozen dataclass with the specified fields."""

    def test_model_info_is_dataclass(self):
        assert dataclasses.is_dataclass(ModelInfo)

    def test_model_info_is_frozen(self):
        info = ModelInfo(
            provider="openai",
            model_id="gpt-4o",
            mode="chat",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.provider = "anthropic"  # type: ignore[misc]

    def test_model_info_required_fields(self):
        info = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        assert info.provider == "openai"
        assert info.model_id == "gpt-4o"
        assert info.mode == "chat"

    def test_model_info_optional_int_fields_default_none(self):
        info = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        assert info.max_tokens is None
        assert info.max_input_tokens is None

    def test_model_info_optional_float_fields_default_none(self):
        info = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        assert info.input_cost_per_token is None
        assert info.output_cost_per_token is None

    def test_model_info_bool_defaults(self):
        info = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        assert info.supports_vision is False
        assert info.supports_function_calling is False
        assert info.supports_streaming is True

    def test_model_info_all_fields_populated(self):
        info = ModelInfo(
            provider="anthropic",
            model_id="claude-3-opus",
            mode="chat",
            max_tokens=4096,
            max_input_tokens=200000,
            input_cost_per_token=0.000015,
            output_cost_per_token=0.000075,
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
        )
        assert info.max_tokens == 4096
        assert info.max_input_tokens == 200000
        assert info.input_cost_per_token == 0.000015
        assert info.output_cost_per_token == 0.000075
        assert info.supports_vision is True
        assert info.supports_function_calling is True

    def test_model_info_missing_required_field_raises(self):
        with pytest.raises(TypeError):
            ModelInfo(provider="openai", model_id="gpt-4o")  # type: ignore[call-arg]


# ===========================================================================
# 2. ProviderInfo dataclass
# ===========================================================================


class TestProviderInfoDataclass:
    def test_provider_info_is_dataclass(self):
        assert dataclasses.is_dataclass(ProviderInfo)

    def test_provider_info_is_frozen(self):
        info = ProviderInfo(id="openai", name="OpenAI", model_count=5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            info.id = "other"  # type: ignore[misc]

    def test_provider_info_fields(self):
        info = ProviderInfo(id="anthropic", name="Anthropic", model_count=12)
        assert info.id == "anthropic"
        assert info.name == "Anthropic"
        assert info.model_count == 12


# ===========================================================================
# 3. ModelCatalogPort protocol
# ===========================================================================


class TestModelCatalogPortProtocol:
    def test_model_catalog_port_is_protocol(self):
        assert issubclass(ModelCatalogPort, Protocol)

    def test_model_catalog_port_is_runtime_checkable(self):
        """ModelCatalogPort should be runtime_checkable for isinstance checks."""
        assert hasattr(ModelCatalogPort, "__protocol_attrs__") or callable(
            getattr(ModelCatalogPort, "_is_runtime_protocol", None)
        )

    def test_litellm_catalog_satisfies_protocol(self):
        """LiteLLMModelCatalog must be a structural subtype of ModelCatalogPort."""
        assert isinstance(LiteLLMModelCatalog(), ModelCatalogPort)

    def test_protocol_has_get_providers(self):
        assert hasattr(ModelCatalogPort, "get_providers")

    def test_protocol_has_get_models(self):
        assert hasattr(ModelCatalogPort, "get_models")

    def test_protocol_has_get_model_info(self):
        assert hasattr(ModelCatalogPort, "get_model_info")

    def test_dummy_satisfies_protocol(self):
        """A plain class with matching methods satisfies the protocol."""

        class DummyCatalog:
            def get_providers(self) -> list:
                return []

            def get_models(self, provider=None, mode=None, capabilities=None) -> list:
                return []

            def get_model_info(self, provider: str, model_id: str):
                return None

        assert isinstance(DummyCatalog(), ModelCatalogPort)


# ===========================================================================
# 4. LiteLLMModelCatalog — loading from litellm.model_cost
# ===========================================================================


FAKE_MODEL_COST = {
    "gpt-4o": {
        "litellm_provider": "openai",
        "mode": "chat",
        "max_tokens": 16384,
        "max_input_tokens": 128000,
        "input_cost_per_token": 0.000005,
        "output_cost_per_token": 0.000015,
        "supports_vision": True,
        "supports_function_calling": True,
    },
    "gpt-3.5-turbo": {
        "litellm_provider": "openai",
        "mode": "chat",
        "max_tokens": 4096,
        "max_input_tokens": 16385,
        "input_cost_per_token": 0.0000005,
        "output_cost_per_token": 0.0000015,
        "supports_function_calling": True,
    },
    "claude-3-opus-20240229": {
        "litellm_provider": "anthropic",
        "mode": "chat",
        "max_tokens": 4096,
        "max_input_tokens": 200000,
        "input_cost_per_token": 0.000015,
        "output_cost_per_token": 0.000075,
        "supports_vision": True,
        "supports_function_calling": True,
    },
    "text-embedding-ada-002": {
        "litellm_provider": "openai",
        "mode": "embedding",
        "max_tokens": None,
        "max_input_tokens": 8191,
        "input_cost_per_token": 0.0000001,
        "output_cost_per_token": 0.0,
    },
    "dall-e-3": {
        "litellm_provider": "openai",
        "mode": "image_generation",
        "max_tokens": None,
        "max_input_tokens": None,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
    },
}


@pytest.fixture
def catalog_with_fake_data():
    """Patch litellm.model_cost with known data and return a fresh catalog."""
    fake_litellm = types.ModuleType("litellm")
    fake_litellm.model_cost = FAKE_MODEL_COST  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"litellm": fake_litellm}):
        return LiteLLMModelCatalog()


class TestLiteLLMModelCatalogLoading:
    def test_catalog_loads_models(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models()
        assert len(models) == 5

    def test_catalog_returns_model_info_instances(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models()
        assert all(isinstance(m, ModelInfo) for m in models)


# ===========================================================================
# 5. get_providers() — deduplication and counts
# ===========================================================================


class TestGetProviders:
    def test_returns_provider_info_list(self, catalog_with_fake_data):
        providers = catalog_with_fake_data.get_providers()
        assert all(isinstance(p, ProviderInfo) for p in providers)

    def test_providers_are_deduplicated(self, catalog_with_fake_data):
        providers = catalog_with_fake_data.get_providers()
        provider_ids = [p.id for p in providers]
        assert len(provider_ids) == len(set(provider_ids))

    def test_provider_count_openai(self, catalog_with_fake_data):
        providers = catalog_with_fake_data.get_providers()
        openai = next(p for p in providers if p.id == "openai")
        assert openai.model_count == 4  # gpt-4o, gpt-3.5-turbo, ada-002, dall-e-3

    def test_provider_count_anthropic(self, catalog_with_fake_data):
        providers = catalog_with_fake_data.get_providers()
        anthropic = next(p for p in providers if p.id == "anthropic")
        assert anthropic.model_count == 1


# ===========================================================================
# 6. get_models() — filtering by provider
# ===========================================================================


class TestGetModelsFilterByProvider:
    def test_filter_by_openai(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(provider="openai")
        assert len(models) == 4
        assert all(m.provider == "openai" for m in models)

    def test_filter_by_anthropic(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(provider="anthropic")
        assert len(models) == 1
        assert models[0].model_id == "claude-3-opus-20240229"

    def test_unknown_provider_returns_empty(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(provider="nonexistent")
        assert models == []


# ===========================================================================
# 7. get_models() — filtering by mode
# ===========================================================================


class TestGetModelsFilterByMode:
    def test_filter_by_chat_mode(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(mode="chat")
        assert len(models) == 3
        assert all(m.mode == "chat" for m in models)

    def test_filter_by_embedding_mode(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(mode="embedding")
        assert len(models) == 1
        assert models[0].model_id == "text-embedding-ada-002"

    def test_filter_by_image_generation_mode(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(mode="image_generation")
        assert len(models) == 1
        assert models[0].model_id == "dall-e-3"


# ===========================================================================
# 8. get_models() — filtering by capabilities
# ===========================================================================


class TestGetModelsFilterByCapabilities:
    def test_filter_vision_true(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(capabilities={"supports_vision": True})
        assert len(models) == 2
        assert all(m.supports_vision for m in models)

    def test_filter_function_calling_true(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(capabilities={"supports_function_calling": True})
        assert len(models) == 3
        assert all(m.supports_function_calling for m in models)

    def test_filter_combined_vision_and_function_calling(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(
            capabilities={
                "supports_vision": True,
                "supports_function_calling": True,
            }
        )
        assert len(models) == 2  # gpt-4o and claude-3-opus

    def test_filter_provider_and_capabilities(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(
            provider="openai",
            capabilities={"supports_vision": True},
        )
        assert len(models) == 1
        assert models[0].model_id == "gpt-4o"

    def test_filter_mode_and_capabilities(self, catalog_with_fake_data):
        models = catalog_with_fake_data.get_models(
            mode="chat",
            capabilities={"supports_function_calling": True},
        )
        assert len(models) == 3


# ===========================================================================
# 9. get_model_info() — specific lookup
# ===========================================================================


class TestGetModelInfo:
    def test_returns_model_info_for_known_model(self, catalog_with_fake_data):
        info = catalog_with_fake_data.get_model_info("openai", "gpt-4o")
        assert info is not None
        assert isinstance(info, ModelInfo)
        assert info.provider == "openai"
        assert info.model_id == "gpt-4o"

    def test_returns_none_for_unknown_model(self, catalog_with_fake_data):
        info = catalog_with_fake_data.get_model_info("openai", "nonexistent-model")
        assert info is None

    def test_returns_none_for_unknown_provider(self, catalog_with_fake_data):
        info = catalog_with_fake_data.get_model_info("nonexistent", "gpt-4o")
        assert info is None

    def test_model_info_has_correct_costs(self, catalog_with_fake_data):
        info = catalog_with_fake_data.get_model_info("openai", "gpt-4o")
        assert info is not None
        assert info.input_cost_per_token == 0.000005
        assert info.output_cost_per_token == 0.000015

    def test_model_info_has_correct_token_limits(self, catalog_with_fake_data):
        info = catalog_with_fake_data.get_model_info("openai", "gpt-4o")
        assert info is not None
        assert info.max_tokens == 16384
        assert info.max_input_tokens == 128000


# ===========================================================================
# 10. Graceful handling of missing/malformed fields
# ===========================================================================


class TestMissingFieldsHandling:
    def test_missing_optional_fields_no_crash(self):
        """Entries with missing optional fields should still produce a valid ModelInfo."""
        sparse_cost = {
            "bare-model": {
                "litellm_provider": "custom",
                "mode": "chat",
                # no max_tokens, no costs, no capability flags
            },
        }
        fake_litellm = types.ModuleType("litellm")
        fake_litellm.model_cost = sparse_cost  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            catalog = LiteLLMModelCatalog()
            models = catalog.get_models()
            assert len(models) == 1
            m = models[0]
            assert m.model_id == "bare-model"
            assert m.max_tokens is None
            assert m.input_cost_per_token is None
            assert m.supports_vision is False

    def test_missing_mode_field_handled(self):
        """Entry missing 'mode' should be handled gracefully (skip or default)."""
        bad_cost = {
            "no-mode-model": {
                "litellm_provider": "custom",
                # no mode key at all
            },
        }
        fake_litellm = types.ModuleType("litellm")
        fake_litellm.model_cost = bad_cost  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            catalog = LiteLLMModelCatalog()
            # Should not crash — either skips or assigns a default
            models = catalog.get_models()
            assert isinstance(models, list)

    def test_missing_provider_field_handled(self):
        """Entry missing 'litellm_provider' should be handled gracefully."""
        bad_cost = {
            "orphan-model": {
                "mode": "chat",
                # no litellm_provider
            },
        }
        fake_litellm = types.ModuleType("litellm")
        fake_litellm.model_cost = bad_cost  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            catalog = LiteLLMModelCatalog()
            models = catalog.get_models()
            assert isinstance(models, list)


# ===========================================================================
# 11. Empty catalog / litellm unavailable
# ===========================================================================


class TestEdgeCases:
    def test_empty_model_cost(self):
        fake_litellm = types.ModuleType("litellm")
        fake_litellm.model_cost = {}  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            catalog = LiteLLMModelCatalog()
            assert catalog.get_models() == []
            assert catalog.get_providers() == []

    def test_litellm_unavailable_does_not_crash(self):
        """If litellm is not installed, catalog should handle gracefully."""
        with patch.dict(sys.modules, {"litellm": None}):
            # Importing or instantiating should not raise an unhandled exception.
            # The implementation may raise a clear error or return empty results.
            try:
                catalog = LiteLLMModelCatalog()
                models = catalog.get_models()
                assert models == []
            except ImportError:
                pass  # Acceptable: a clear ImportError is fine


# ===========================================================================
# 12. Cache behavior
# ===========================================================================


class TestCacheTTL:
    def test_catalog_caches_results(self):
        """Repeated calls should not re-parse litellm.model_cost."""
        fake_litellm = types.ModuleType("litellm")
        fake_litellm.model_cost = FAKE_MODEL_COST  # type: ignore[attr-defined]
        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            catalog = LiteLLMModelCatalog()
            first = catalog.get_models()
            second = catalog.get_models()
            # Same list object if cached
            assert first is second


# ===========================================================================
# 13. Import boundary — litellm must not leak
# ===========================================================================


class TestImportBoundary:
    def test_model_info_does_not_import_litellm(self):
        """ModelInfo should be importable without litellm in sys.modules."""
        # If the module itself imports litellm at top level, this would fail.
        # We just verify ModelInfo is a plain dataclass with no litellm dependency.
        assert not any("litellm" in str(base) for base in ModelInfo.__mro__)

    def test_provider_info_does_not_import_litellm(self):
        assert not any("litellm" in str(base) for base in ProviderInfo.__mro__)

    def test_model_catalog_module_does_not_top_level_import_litellm(self):
        """The model_catalog module should lazy-import litellm, not at module top level."""
        import runsight_core.llm.model_catalog as mc_module

        source_file = mc_module.__file__
        assert source_file is not None
        with open(source_file, "r") as f:
            source = f.read()
        # Top-level `import litellm` or `from litellm import ...` outside class/function
        # is forbidden. litellm should only be imported inside LiteLLMModelCatalog methods.
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("import litellm") or stripped.startswith("from litellm"):
                # Check indentation — top-level means no leading whitespace
                if not line.startswith((" ", "\t")):
                    pytest.fail(f"Found top-level litellm import at line {i + 1}: {line!r}")
