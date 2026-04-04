import time
from typing import List, Optional

import httpx
from runsight_core.security import SSRFError, validate_ssrf

from ...core.secrets import SecretsEnvLoader
from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...domain.value_objects import ProviderEntity

# Infer provider type from name (case-insensitive)
_NAME_TO_TYPE = {
    "openai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "google": "google",
    "gemini": "google",
    "azure": "azure_openai",
    "bedrock": "aws_bedrock",
    "mistral": "mistral",
    "cohere": "cohere",
    "groq": "groq",
    "together": "together",
    "ollama": "ollama",
}


def _infer_provider_type(name: str) -> str:
    name_lower = name.lower()
    for keyword, ptype in _NAME_TO_TYPE.items():
        if keyword in name_lower:
            return ptype
    return "custom"


def _parse_models(body: dict, provider_type: str) -> list[str]:
    """Extract model ID strings from provider-specific list-models responses."""
    try:
        if provider_type == "ollama":
            # { "models": [{ "name": "llama3", ... }] }
            return sorted(m["name"] for m in body.get("models", []))
        if provider_type == "google":
            # { "models": [{ "name": "models/gemini-pro", ... }] }
            return sorted(m["name"].removeprefix("models/") for m in body.get("models", []))
        # OpenAI-compatible: { "data": [{ "id": "gpt-4o", ... }] }
        return sorted(m["id"] for m in body.get("data", []))
    except (KeyError, TypeError):
        return []


def _build_provider_test_result(
    *,
    success: bool,
    message: str,
    models: Optional[list[str]] = None,
    latency_ms: float = 0.0,
) -> dict:
    normalized_models = models or []
    return {
        "success": success,
        "message": message,
        "models": normalized_models,
        "model_count": len(normalized_models),
        "latency_ms": latency_ms,
    }


class ProviderService:
    def __init__(self, repo: FileSystemProviderRepo, secrets: SecretsEnvLoader):
        self.repo = repo
        self.secrets = secrets

    def list_providers(self) -> List[ProviderEntity]:
        return self.repo.list_all()

    def get_provider(self, provider_id: str) -> Optional[ProviderEntity]:
        return self.repo.get_by_id(provider_id)

    def create_provider(
        self,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> ProviderEntity:
        if provider_type is None:
            provider_type = _infer_provider_type(name)

        api_key_ref: Optional[str] = None
        if api_key:
            api_key_ref = self.secrets.store_key(provider_type, api_key)

        data = {
            "name": name,
            "type": provider_type,
            "api_key": api_key_ref,
            "base_url": base_url,
            "status": "unknown",
            "is_active": True,
        }
        return self.repo.create(data)

    def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ProviderEntity]:
        provider = self.repo.get_by_id(provider_id)
        if not provider:
            return None

        update_data: dict = {}
        if name is not None:
            update_data["name"] = name
        if api_key is not None:
            if api_key:
                api_key_ref = self.secrets.store_key(provider.type, api_key)
                update_data["api_key"] = api_key_ref
            else:
                update_data["api_key"] = None
        if base_url is not None:
            update_data["base_url"] = base_url
        if is_active is not None:
            update_data["is_active"] = is_active

        update_data["updated_at"] = time.time()
        return self.repo.update(provider_id, update_data)

    def delete_provider(self, provider_id: str) -> bool:
        provider = self.repo.get_by_id(provider_id)
        if provider and provider.api_key:
            self.secrets.remove_key(provider.api_key)
        return self.repo.delete(provider_id)

    async def _execute_connection_test(
        self,
        *,
        provider_type: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> dict:
        started_at = time.perf_counter()

        def finalize(*, success: bool, message: str, models: Optional[list[str]] = None) -> dict:
            latency_ms = (time.perf_counter() - started_at) * 1000
            return _build_provider_test_result(
                success=success,
                message=message,
                models=models,
                latency_ms=latency_ms,
            )

        if not api_key and provider_type != "ollama":
            return finalize(success=False, message="No API key configured")

        allow_private = provider_type == "ollama"
        try:
            if provider_type in ("openai", "azure_openai"):
                base = base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                await validate_ssrf(url, allow_private=allow_private)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10,
                    )
            elif provider_type == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                await validate_ssrf(url, allow_private=allow_private)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                        },
                        timeout=10,
                    )
            elif provider_type == "google":
                url = "https://generativelanguage.googleapis.com/v1beta/models"
                await validate_ssrf(url, allow_private=allow_private)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        headers={"x-goog-api-key": api_key},
                        timeout=10,
                    )
            elif provider_type == "ollama":
                base = base_url or "http://localhost:11434"
                url = f"{base}/api/tags"
                await validate_ssrf(url, allow_private=allow_private)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=10)
            else:
                base = base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                await validate_ssrf(url, allow_private=allow_private)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10,
                    )

            success = resp.status_code == 200
            models: list[str] = []
            if success:
                models = _parse_models(resp.json(), provider_type)

            msg = (
                f"Connected — {len(models)} models available"
                if success
                else f"Connection failed (HTTP {resp.status_code})"
            )
            return finalize(success=success, message=msg, models=models)
        except SSRFError as e:
            return finalize(success=False, message=f"SSRF blocked: {str(e)}")
        except Exception as e:
            return finalize(success=False, message=f"Connection failed: {str(e)}")

    async def test_credentials(
        self,
        *,
        provider_id: Optional[str] = None,
        provider_type: Optional[str] = None,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> dict:
        existing_provider: Optional[ProviderEntity] = None
        if provider_id:
            existing_provider = self.repo.get_by_id(provider_id)
            if not existing_provider:
                return _build_provider_test_result(success=False, message="Provider not found")

        resolved_provider_type = provider_type
        if not resolved_provider_type and existing_provider:
            resolved_provider_type = existing_provider.type
        if not resolved_provider_type and name:
            resolved_provider_type = _infer_provider_type(name)
        if not resolved_provider_type:
            return _build_provider_test_result(success=False, message="Provider type is required")

        resolved_api_key = api_key
        if not resolved_api_key and existing_provider and existing_provider.api_key:
            resolved_api_key = self.secrets.resolve(existing_provider.api_key)

        resolved_base_url = base_url
        if resolved_base_url is None and existing_provider:
            resolved_base_url = existing_provider.base_url

        return await self._execute_connection_test(
            provider_type=resolved_provider_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
        )

    async def test_connection(self, provider_id: str) -> dict:
        provider = self.repo.get_by_id(provider_id)
        if not provider:
            return _build_provider_test_result(success=False, message="Provider not found")

        result = await self.test_credentials(provider_id=provider_id)
        if result.get("message") == "No API key configured":
            return result

        update_data = {
            "status": "connected" if result.get("success") else "error",
            "models": result.get("models", []),
            "last_status_check": time.time(),
            "updated_at": time.time(),
        }
        self.repo.update(provider_id, update_data)
        return result
