"""Model catalog dataclass and protocol contracts."""

from __future__ import annotations

import dataclasses
from typing import Protocol

import pytest
from runsight_core.llm.model_catalog import (
    LiteLLMModelCatalog,
    ModelCatalogPort,
    ModelInfo,
    ProviderInfo,
)


def test_model_info_is_frozen_dataclass_with_defaults() -> None:
    info = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")

    assert dataclasses.is_dataclass(ModelInfo)
    assert info.max_tokens is None
    assert info.input_cost_per_token is None
    assert info.supports_vision is False
    assert info.supports_function_calling is False
    assert info.supports_streaming is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.provider = "anthropic"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ModelInfo(provider="openai", model_id="gpt-4o")  # type: ignore[call-arg]


def test_provider_info_is_frozen_dataclass() -> None:
    info = ProviderInfo(id="anthropic", name="Anthropic", model_count=12)

    assert dataclasses.is_dataclass(ProviderInfo)
    assert info.id == "anthropic"
    assert info.name == "Anthropic"
    assert info.model_count == 12
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.id = "other"  # type: ignore[misc]


def test_model_catalog_port_is_runtime_protocol() -> None:
    class DummyCatalog:
        def get_providers(self) -> list:
            return []

        def get_models(self, provider=None, mode=None, capabilities=None) -> list:
            return []

        def get_model_info(self, provider: str, model_id: str):
            return None

    assert issubclass(ModelCatalogPort, Protocol)
    assert isinstance(LiteLLMModelCatalog(), ModelCatalogPort)
    assert isinstance(DummyCatalog(), ModelCatalogPort)
