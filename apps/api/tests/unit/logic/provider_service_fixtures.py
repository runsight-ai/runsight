"""Shared provider service fixtures isolated to tmp_path secrets."""

import pytest

from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.logic.services.provider_service import ProviderService

_PROVIDER_SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_provider_secret_env(monkeypatch):
    """Keep SecretsEnvLoader tests on temp secrets.env, never shell credentials."""
    for name in _PROVIDER_SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def tmp_base(tmp_path):
    """Return a temp base path for filesystem repos."""
    return str(tmp_path)


@pytest.fixture
def secrets(tmp_base):
    """Create a SecretsEnvLoader rooted at a temporary directory."""
    return SecretsEnvLoader(base_path=tmp_base)


@pytest.fixture
def provider_repo(tmp_base):
    """Create a FileSystemProviderRepo rooted at a temporary directory."""
    return FileSystemProviderRepo(base_path=tmp_base)


@pytest.fixture
def service(provider_repo, secrets):
    """Create a ProviderService wired with filesystem repo + secrets loader."""
    return ProviderService(provider_repo, secrets)


# ===========================================================================
# 1. ProviderService constructor accepts SecretsEnvLoader
# ===========================================================================
