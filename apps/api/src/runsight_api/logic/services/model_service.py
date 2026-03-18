"""Service layer for model catalog queries (RUN-151)."""

from __future__ import annotations

import logging

from runsight_core.llm.model_catalog import ModelCatalogPort, ModelInfo

logger = logging.getLogger(__name__)


class ModelService:
    """Bridges the model catalog port with configured-provider filtering."""

    def __init__(self, catalog: ModelCatalogPort, provider_repo) -> None:
        self._catalog = catalog
        self._provider_repo = provider_repo

    def _list_configured_providers(self) -> list:
        """Return configured providers, gracefully handling DB errors."""
        try:
            return self._provider_repo.list_all()
        except Exception:
            logger.debug("Could not query provider table; treating as empty.", exc_info=True)
            return []

    def get_available_models(
        self,
        *,
        provider: str | None = None,
        mode: str | None = None,
        supports_vision: bool | None = None,
        supports_function_calling: bool | None = None,
        all_providers: bool = False,
    ) -> list[ModelInfo]:
        """Return catalog models, optionally filtered.

        If *all_providers* is False (default), only models whose provider
        matches a configured provider (from provider_repo) are returned.
        """
        models = self._catalog.get_models()

        if provider is not None:
            models = [m for m in models if m.provider == provider]
        if mode is not None:
            models = [m for m in models if m.mode == mode]
        if supports_vision is not None:
            models = [m for m in models if m.supports_vision == supports_vision]
        if supports_function_calling is not None:
            models = [m for m in models if m.supports_function_calling == supports_function_calling]

        if not all_providers:
            configured = self._list_configured_providers()
            configured_types = {p.type for p in configured}
            models = [m for m in models if m.provider in configured_types]

        return models

    def get_provider_summary(self) -> list[dict]:
        """Return provider summaries with is_configured flag."""
        providers = self._catalog.get_providers()
        configured = self._list_configured_providers()
        configured_types = {p.type for p in configured}

        return [
            {
                "id": p.id,
                "name": p.name,
                "model_count": p.model_count,
                "is_configured": p.id in configured_types,
            }
            for p in providers
        ]
