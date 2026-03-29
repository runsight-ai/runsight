"""ModelCatalogPort protocol and LiteLLMModelCatalog implementation.

RUN-150: Provides a domain-agnostic protocol for querying available LLM models
and a concrete implementation backed by litellm's model_cost dictionary.
"""

from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable


@dataclasses.dataclass(frozen=True)
class ModelInfo:
    """Immutable descriptor for a single LLM model."""

    provider: str
    model_id: str
    mode: str

    max_tokens: int | None = None
    max_input_tokens: int | None = None
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None

    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True


@dataclasses.dataclass(frozen=True)
class ProviderInfo:
    """Immutable descriptor for an LLM provider."""

    id: str
    name: str
    model_count: int


@runtime_checkable
class ModelCatalogPort(Protocol):
    """Port for querying available LLM models."""

    def get_providers(self) -> list[ProviderInfo]: ...

    def get_models(
        self,
        provider: str | None = None,
        mode: str | None = None,
        capabilities: dict | None = None,
    ) -> list[ModelInfo]: ...

    def get_model_info(self, provider: str, model_id: str) -> ModelInfo | None: ...


class LiteLLMModelCatalog:
    """ModelCatalogPort implementation backed by litellm.model_cost."""

    def __init__(self) -> None:
        self._models: list[ModelInfo] | None = None
        self._load()

    def _load(self) -> None:
        """Parse litellm.model_cost into ModelInfo instances (lazy litellm import)."""
        try:
            import litellm  # noqa: F811
        except (ImportError, ModuleNotFoundError):
            self._models = []
            return

        model_cost: dict = getattr(litellm, "model_cost", {})
        models: list[ModelInfo] = []

        for model_key, entry in model_cost.items():
            if not isinstance(entry, dict):
                continue

            provider = entry.get("litellm_provider", "unknown")
            mode = entry.get("mode", "unknown")

            models.append(
                ModelInfo(
                    provider=provider,
                    model_id=model_key,
                    mode=mode,
                    max_tokens=entry.get("max_tokens"),
                    max_input_tokens=entry.get("max_input_tokens"),
                    input_cost_per_token=entry.get("input_cost_per_token"),
                    output_cost_per_token=entry.get("output_cost_per_token"),
                    supports_vision=bool(entry.get("supports_vision", False)),
                    supports_function_calling=bool(entry.get("supports_function_calling", False)),
                    supports_streaming=bool(entry.get("supports_streaming", True)),
                )
            )

        self._models = models

    def get_providers(self) -> list[ProviderInfo]:
        """Return deduplicated provider list with model counts."""
        models = self.get_models()
        counts: dict[str, int] = {}
        for m in models:
            counts[m.provider] = counts.get(m.provider, 0) + 1

        return [
            ProviderInfo(id=pid, name=pid.capitalize(), model_count=count)
            for pid, count in counts.items()
        ]

    def get_models(
        self,
        provider: str | None = None,
        mode: str | None = None,
        capabilities: dict | None = None,
    ) -> list[ModelInfo]:
        """Return models, optionally filtered by provider, mode, and capabilities."""
        assert self._models is not None
        result = self._models

        if provider is not None:
            result = [m for m in result if m.provider == provider]

        if mode is not None:
            result = [m for m in result if m.mode == mode]

        if capabilities:
            for cap_key, cap_val in capabilities.items():
                result = [m for m in result if getattr(m, cap_key, None) == cap_val]

        return result

    def get_model_info(self, provider: str, model_id: str) -> ModelInfo | None:
        """Look up a specific model by provider and model_id."""
        for m in self.get_models():
            if m.provider == provider and m.model_id == model_id:
                return m
        return None
