"""LiteLLM-backed model catalog loading and filtering."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest
from model_catalog_helpers import FAKE_MODEL_COST, patched_litellm_model_cost
from runsight_core.llm.model_catalog import LiteLLMModelCatalog, ModelInfo, ProviderInfo


@pytest.fixture
def catalog() -> LiteLLMModelCatalog:
    with patched_litellm_model_cost(FAKE_MODEL_COST):
        yield LiteLLMModelCatalog()


def test_catalog_loads_model_info_instances(catalog: LiteLLMModelCatalog) -> None:
    models = catalog.get_models()

    assert len(models) == 5
    assert all(isinstance(model, ModelInfo) for model in models)


def test_get_providers_deduplicates_and_counts_models(catalog: LiteLLMModelCatalog) -> None:
    providers = catalog.get_providers()

    assert all(isinstance(provider, ProviderInfo) for provider in providers)
    counts = {provider.id: provider.model_count for provider in providers}
    assert counts == {"anthropic": 1, "openai": 4}


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"provider": "openai"}, {"gpt-4o", "gpt-3.5-turbo", "text-embedding-ada-002", "dall-e-3"}),
        ({"provider": "anthropic"}, {"claude-3-opus-20240229"}),
        ({"mode": "embedding"}, {"text-embedding-ada-002"}),
        ({"mode": "image_generation"}, {"dall-e-3"}),
        ({"capabilities": {"supports_vision": True}}, {"gpt-4o", "claude-3-opus-20240229"}),
        (
            {"provider": "openai", "capabilities": {"supports_vision": True}},
            {"gpt-4o"},
        ),
    ],
)
def test_get_models_filters_by_provider_mode_and_capabilities(
    catalog: LiteLLMModelCatalog,
    filters: dict,
    expected_ids: set[str],
) -> None:
    models = catalog.get_models(**filters)

    assert {model.model_id for model in models} == expected_ids


def test_get_model_info_returns_known_model_costs_and_limits(catalog: LiteLLMModelCatalog) -> None:
    info = catalog.get_model_info("openai", "gpt-4o")

    assert info is not None
    assert info.input_cost_per_token == pytest.approx(0.000005)
    assert info.output_cost_per_token == pytest.approx(0.000015)
    assert info.max_tokens == 16384
    assert info.max_input_tokens == 128000
    assert catalog.get_model_info("openai", "missing") is None
    assert catalog.get_model_info("missing", "gpt-4o") is None


@pytest.mark.parametrize(
    "model_cost",
    [
        {"bare-model": {"litellm_provider": "custom", "mode": "chat"}},
        {"no-mode-model": {"litellm_provider": "custom"}},
        {"orphan-model": {"mode": "chat"}},
        {},
    ],
)
def test_missing_or_empty_litellm_fields_do_not_crash(model_cost: dict) -> None:
    with patched_litellm_model_cost(model_cost):
        catalog = LiteLLMModelCatalog()
        assert isinstance(catalog.get_models(), list)
        assert isinstance(catalog.get_providers(), list)


def test_litellm_unavailable_returns_empty_or_clear_importerror() -> None:
    with patch.dict(sys.modules, {"litellm": None}):
        try:
            assert LiteLLMModelCatalog().get_models() == []
        except ImportError:
            pass


def test_catalog_caches_loaded_model_list() -> None:
    with patched_litellm_model_cost(FAKE_MODEL_COST):
        catalog = LiteLLMModelCatalog()
        assert catalog.get_models() is catalog.get_models()


def test_model_catalog_module_lazy_imports_litellm() -> None:
    import ast

    import runsight_core.llm.model_catalog as model_catalog_module

    source_file = model_catalog_module.__file__
    assert source_file is not None
    tree = ast.parse(open(source_file, encoding="utf-8").read())

    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name == "litellm" for alias in node.names)
    ]
    assert top_level_imports == []
