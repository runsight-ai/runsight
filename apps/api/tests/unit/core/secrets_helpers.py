"""Shared fixtures for SecretsEnvLoader tests."""

from pathlib import Path

import pytest

from runsight_api.core.secrets import SecretsEnvLoader

SECRET_ENV_NAMES = (
    "MY_API_KEY",
    "FOO",
    "MY_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "NONEXISTENT_API_KEY",
)


@pytest.fixture(name="clear_secret_env", autouse=True)
def clear_secret_env_fixture(monkeypatch):
    """Keep tests isolated from shell credentials and real environment state."""
    for name in SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(name="loader")
def loader_fixture(tmp_path):
    """Create a SecretsEnvLoader rooted at a temporary directory."""
    return SecretsEnvLoader(base_path=str(tmp_path))


@pytest.fixture(name="secrets_file")
def secrets_file_fixture(tmp_path):
    """Return the expected secrets.env file path."""
    return tmp_path / ".runsight" / "secrets.env"


def write_secrets_file(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
