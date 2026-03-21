import time
import uuid
from typing import List, Optional

import httpx

from runsight_core.security import SSRFError, validate_ssrf

from ...data.repositories.provider_repo import ProviderRepository
from ...domain.entities.provider import Provider
from ...core.encryption import decrypt, encrypt

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
    def __init__(self, repo: ProviderRepository):
        self.repo = repo

    def list_providers(self) -> List[Provider]:
        return self.repo.list_all()

    def get_provider(self, provider_id: str) -> Optional[Provider]:
        return self.repo.get_by_id(provider_id)

    def create_provider(
        self,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> Provider:
        if provider_type is None:
            provider_type = _infer_provider_type(name)
        provider = Provider(
            id=f"prov_{uuid.uuid4().hex[:12]}",
            name=name,
            type=provider_type,
            api_key_encrypted=encrypt(api_key) if api_key else None,
            base_url=base_url,
            status="unknown",
            is_active=True,
        )
        return self.repo.create(provider)

    def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Optional[Provider]:
        provider = self.repo.get_by_id(provider_id)
        if not provider:
            return None
        if name is not None:
            provider.name = name
        if api_key is not None:
            provider.api_key_encrypted = encrypt(api_key) if api_key else None
        if base_url is not None:
            provider.base_url = base_url
        provider.updated_at = time.time()
        return self.repo.update(provider)

    def delete_provider(self, provider_id: str) -> bool:
        return self.repo.delete(provider_id)

    def test_connection(self, provider_id: str) -> dict:
        provider = self.repo.get_by_id(provider_id)
        if not provider:
            return {"success": False, "message": "Provider not found"}

        if not provider.api_key_encrypted and provider.type != "ollama":
            return {"success": False, "message": "No API key configured"}

        api_key = decrypt(provider.api_key_encrypted) if provider.api_key_encrypted else None
        allow_private = provider.type == "ollama"

        try:
            if provider.type in ("openai", "azure_openai"):
                base = provider.base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
            elif provider.type == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                validate_ssrf(url, allow_private=allow_private)
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
                validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(url, timeout=10)
            elif provider.type == "ollama":
                base = provider.base_url or "http://localhost:11434"
                url = f"{base}/api/tags"
                validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(url, timeout=10)
            else:
                base = provider.base_url or "https://api.openai.com/v1"
                url = f"{base}/models"
                validate_ssrf(url, allow_private=allow_private)
                resp = httpx.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )

            success = resp.status_code == 200
            models: list[str] = []
            if success:
                models = _parse_models(resp.json(), provider.type)

            provider.status = "connected" if success else "error"
            provider.models = models
            provider.last_status_check = time.time()
            provider.updated_at = time.time()
            self.repo.update(provider)

            msg = (
                f"Connected — {len(models)} models available"
                if success
                else f"Connection failed (HTTP {resp.status_code})"
            )
            return {"success": success, "message": msg, "models": models}
        except SSRFError as e:
            return {"success": False, "message": f"SSRF blocked: {str(e)}"}
        except Exception as e:
            provider.status = "error"
            provider.last_status_check = time.time()
            provider.updated_at = time.time()
            self.repo.update(provider)
            return {"success": False, "message": f"Connection failed: {str(e)}"}
