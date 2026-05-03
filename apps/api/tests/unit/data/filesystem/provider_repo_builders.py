VALID_PROVIDER_DATA = {
    "id": "fixture-provider",
    "kind": "provider",
    "name": "Fixture Provider",
    "type": "fixture-provider",
    "api_key": "${DUMMY_PROVIDER_KEY}",
    "base_url": "http://localhost/fixture-provider/v1",
    "is_active": True,
    "status": "connected",
    "models": ["fixture-chat-model", "fixture-small-model"],
}


def _slugify(name: str) -> str:
    import re

    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "provider"


def _make_provider_data(**overrides):
    data = dict(VALID_PROVIDER_DATA)
    data.update(overrides)
    if "name" in overrides and "id" not in overrides:
        data["id"] = _slugify(overrides["name"])
    return data


def _ensure_providers_dir(providers_dir):
    providers_dir.mkdir(parents=True, exist_ok=True)
