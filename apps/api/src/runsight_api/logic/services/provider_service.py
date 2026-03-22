import time
from typing import List, Optional

import httpx

from runsight_core.security import SSRFError, validate_ssrf

from ...core.secrets import SecretsEnvLoader
from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...domain.value_objects import ProviderEntity

# Legacy stubs — kept so negative-assertion tests can patch them to verify they're never called
encrypt = None
decrypt = None

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

        update_data["updated_at"] = time.time()
        return self.repo.update(provider_id, update_data)

    def delete_provider(self, provider_id: str) -> bool:
        return self.repo.delete(provider_id)

    async def test_connection(self, provider_id: str) -> dict:
        provider = self.repo.get_by_id(provider_id)
        if not provider:
            return {"success": False, "message": "Provider not found"}

        has_key = provider.api_key and self.secrets.is_configured(provider.api_key)
        if not has_key and provider.type != "ollama":
            return {"success": False, "message": "No API key configured"}

        api_key = self.secrets.resolve(provider.api_key) if provider.api_key else None
        allow_private = provider.type == "ollama"

        try:
            if provider.type in ("openai", "azure_openai"):
                base = provider.base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                await validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
            elif provider.type == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                await validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(
                    url,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    timeout=10,
                )
            elif provider.type == "google":
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                await validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(url, timeout=10)
            elif provider.type == "ollama":
                base = provider.base_url or "http://localhost:11434"
                url = f"{base}/api/tags"
                await validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(url, timeout=10)
            else:
                base = provider.base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                await validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )

            success = resp.status_code == 200
            models: list[str] = []
            if success:
                models = _parse_models(resp.json(), provider.type)

            update_data = {
                "status": "connected" if success else "error",
                "models": models,
                "last_status_check": time.time(),
                "updated_at": time.time(),
            }
            self.repo.update(provider_id, update_data)

            msg = (
                f"Connected — {len(models)} models available"
                if success
                else f"Connection failed (HTTP {resp.status_code})"
            )
            return {"success": success, "message": msg, "models": models}
        except SSRFError as e:
            return {"success": False, "message": f"SSRF blocked: {str(e)}"}
        except Exception as e:
            update_data = {
                "status": "error",
                "last_status_check": time.time(),
                "updated_at": time.time(),
            }
            self.repo.update(provider_id, update_data)
            return {"success": False, "message": f"Connection failed: {str(e)}"}
