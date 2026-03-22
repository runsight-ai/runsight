"""
Red tests for RUN-234: SecretsEnvLoader — read/write .runsight/secrets.env.

Tests the public API of SecretsEnvLoader:
  resolve, store_key, remove_key, is_configured

All tests should FAIL (ImportError) until the implementation is written.

Acceptance criteria covered:
  - Resolution order: os.environ → secrets.env → None
  - store_key writes to secrets.env and returns ${ENV_VAR} reference
  - remove_key removes the line from secrets.env
  - File created on first store_key with '# Managed by Runsight' header
  - Values with = signs handled correctly (split on first = only)
  - Real env var takes precedence over secrets.env value
  - Atomic writes
  - Unit tests for resolution order, store/remove, missing file, env var override
"""

import os

import pytest

from runsight_api.core.secrets import SecretsEnvLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loader(tmp_path):
    """Create a SecretsEnvLoader rooted at a temporary directory."""
    return SecretsEnvLoader(base_path=str(tmp_path))


@pytest.fixture
def secrets_file(tmp_path):
    """Return the expected secrets.env file path."""
    return tmp_path / ".runsight" / "secrets.env"


# ===========================================================================
# AC: Resolution order — os.environ → secrets.env → None
# ===========================================================================


class TestResolveOrder:
    def test_resolve_returns_none_when_not_configured_anywhere(self, loader):
        """resolve must return None when the var is not in env or secrets.env."""
        result = loader.resolve("${NONEXISTENT_API_KEY}")
        assert result is None

    def test_resolve_returns_value_from_secrets_env(self, loader, secrets_file):
        """resolve must return the value from secrets.env when not in os.environ."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text("# Managed by Runsight\nMY_API_KEY=sk-from-file\n")

        result = loader.resolve("${MY_API_KEY}")
        assert result == "sk-from-file"

    def test_resolve_returns_value_from_env_var(self, loader, monkeypatch):
        """resolve must return the os.environ value when set."""
        monkeypatch.setenv("MY_API_KEY", "sk-from-env")

        result = loader.resolve("${MY_API_KEY}")
        assert result == "sk-from-env"

    def test_env_var_takes_precedence_over_secrets_env(self, loader, secrets_file, monkeypatch):
        """Real env var must take precedence over secrets.env value."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text("# Managed by Runsight\nMY_API_KEY=sk-from-file\n")
        monkeypatch.setenv("MY_API_KEY", "sk-from-env")

        result = loader.resolve("${MY_API_KEY}")
        assert result == "sk-from-env"

    def test_resolve_strips_dollar_braces(self, loader, monkeypatch):
        """resolve('${FOO}') must look up 'FOO' in env/file, not '${FOO}'."""
        monkeypatch.setenv("FOO", "bar")
        result = loader.resolve("${FOO}")
        assert result == "bar"


# ===========================================================================
# AC: store_key writes to secrets.env and returns ${ENV_VAR} reference
# ===========================================================================


class TestStoreKey:
    def test_store_key_returns_env_var_reference(self, loader):
        """store_key must return the ${ENV_VAR} reference string."""
        ref = loader.store_key("openai", "sk-abc123")
        assert ref == "${OPENAI_API_KEY}"

    def test_store_key_writes_to_secrets_file(self, loader, secrets_file):
        """store_key must persist the key=value to secrets.env."""
        loader.store_key("openai", "sk-abc123")
        assert secrets_file.exists()

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY=sk-abc123" in content

    def test_store_key_uppercases_provider_type(self, loader, secrets_file):
        """Provider type must be uppercased in the env var name."""
        loader.store_key("anthropic", "sk-ant-123")

        content = secrets_file.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-123" in content

    def test_store_key_handles_underscore_provider(self, loader, secrets_file):
        """Provider types with underscores must map correctly (e.g. azure_openai → AZURE_OPENAI_API_KEY)."""
        ref = loader.store_key("azure_openai", "sk-azure-123")
        assert ref == "${AZURE_OPENAI_API_KEY}"

        content = secrets_file.read_text()
        assert "AZURE_OPENAI_API_KEY=sk-azure-123" in content

    def test_store_key_overwrites_existing_key(self, loader, secrets_file):
        """Calling store_key again for the same provider must update the value."""
        loader.store_key("openai", "sk-old")
        loader.store_key("openai", "sk-new")

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY=sk-new" in content
        # Old value must not be present
        assert "sk-old" not in content

    def test_store_key_preserves_other_keys(self, loader, secrets_file):
        """Storing a new key must not remove existing keys for other providers."""
        loader.store_key("openai", "sk-openai")
        loader.store_key("anthropic", "sk-anthropic")

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY=sk-openai" in content
        assert "ANTHROPIC_API_KEY=sk-anthropic" in content

    def test_store_key_can_resolve_afterwards(self, loader):
        """After store_key, resolve must return the stored value."""
        loader.store_key("openai", "sk-abc123")
        result = loader.resolve("${OPENAI_API_KEY}")
        assert result == "sk-abc123"


# ===========================================================================
# AC: File created on first store_key with '# Managed by Runsight' header
# ===========================================================================


class TestFileCreation:
    def test_file_created_on_first_store(self, loader, secrets_file):
        """secrets.env must be created on the first store_key call."""
        assert not secrets_file.exists()

        loader.store_key("openai", "sk-abc123")

        assert secrets_file.exists()

    def test_file_has_managed_header(self, loader, secrets_file):
        """secrets.env must start with '# Managed by Runsight' header."""
        loader.store_key("openai", "sk-abc123")

        content = secrets_file.read_text()
        first_line = content.split("\n")[0]
        assert first_line == "# Managed by Runsight"

    def test_runsight_dir_created_if_missing(self, loader, tmp_path):
        """The .runsight/ directory must be auto-created if it doesn't exist."""
        runsight_dir = tmp_path / ".runsight"
        assert not runsight_dir.exists()

        loader.store_key("openai", "sk-abc123")

        assert runsight_dir.exists()
        assert runsight_dir.is_dir()

    def test_second_store_preserves_header(self, loader, secrets_file):
        """Subsequent store_key calls must not duplicate the header."""
        loader.store_key("openai", "sk-abc")
        loader.store_key("anthropic", "sk-ant")

        content = secrets_file.read_text()
        assert content.count("# Managed by Runsight") == 1


# ===========================================================================
# AC: remove_key removes the line from secrets.env
# ===========================================================================


class TestRemoveKey:
    def test_remove_key_removes_line(self, loader, secrets_file):
        """remove_key must remove the matching line from secrets.env."""
        loader.store_key("openai", "sk-abc123")
        loader.remove_key("${OPENAI_API_KEY}")

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY" not in content

    def test_remove_key_preserves_other_keys(self, loader, secrets_file):
        """remove_key must not affect other keys in secrets.env."""
        loader.store_key("openai", "sk-openai")
        loader.store_key("anthropic", "sk-anthropic")

        loader.remove_key("${OPENAI_API_KEY}")

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY" not in content
        assert "ANTHROPIC_API_KEY=sk-anthropic" in content

    def test_remove_key_no_error_when_key_missing(self, loader):
        """remove_key must not raise when the key does not exist in secrets.env."""
        loader.store_key("openai", "sk-abc123")
        # Should not raise
        loader.remove_key("${NONEXISTENT_API_KEY}")

    def test_remove_key_no_error_when_file_missing(self, loader):
        """remove_key must not raise when secrets.env does not exist at all."""
        # No store_key called, so file does not exist
        loader.remove_key("${OPENAI_API_KEY}")

    def test_remove_then_is_configured_returns_false(self, loader):
        """After removing a key, is_configured must return False."""
        loader.store_key("openai", "sk-abc123")
        loader.remove_key("${OPENAI_API_KEY}")
        assert loader.is_configured("${OPENAI_API_KEY}") is False

    def test_remove_then_resolve_returns_none(self, loader):
        """After removing a key, resolve must return None (assuming no env var)."""
        loader.store_key("openai", "sk-abc123")
        loader.remove_key("${OPENAI_API_KEY}")
        assert loader.resolve("${OPENAI_API_KEY}") is None


# ===========================================================================
# AC: is_configured returns True/False
# ===========================================================================


class TestIsConfigured:
    def test_is_configured_returns_true_when_in_secrets_env(self, loader):
        """is_configured must return True when the key exists in secrets.env."""
        loader.store_key("openai", "sk-abc123")
        assert loader.is_configured("${OPENAI_API_KEY}") is True

    def test_is_configured_returns_true_when_in_env_var(self, loader, monkeypatch):
        """is_configured must return True when the key exists as an env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        assert loader.is_configured("${OPENAI_API_KEY}") is True

    def test_is_configured_returns_false_when_nowhere(self, loader):
        """is_configured must return False when the key is in neither location."""
        assert loader.is_configured("${NONEXISTENT_API_KEY}") is False

    def test_is_configured_returns_false_when_file_missing(self, loader):
        """is_configured must return False when secrets.env does not exist."""
        assert loader.is_configured("${OPENAI_API_KEY}") is False


# ===========================================================================
# AC: Values with = signs handled correctly (split on first = only)
# ===========================================================================


class TestValuesWithEquals:
    def test_store_and_resolve_value_with_equals(self, loader):
        """Values containing '=' (e.g. base64 keys) must round-trip correctly."""
        base64_key = "sk-abc123+def456/ghi789=="
        loader.store_key("openai", base64_key)
        result = loader.resolve("${OPENAI_API_KEY}")
        assert result == base64_key

    def test_value_with_multiple_equals_in_file(self, loader, secrets_file):
        """A value with multiple = must be stored correctly (split on first = only)."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text("# Managed by Runsight\nMY_KEY=abc=def=ghi\n")

        result = loader.resolve("${MY_KEY}")
        assert result == "abc=def=ghi"

    def test_store_value_with_equals_preserves_full_value(self, loader, secrets_file):
        """store_key must write the full value including = signs."""
        loader.store_key("openai", "a=b=c")

        content = secrets_file.read_text()
        assert "OPENAI_API_KEY=a=b=c" in content


# ===========================================================================
# Edge case: Missing .runsight/secrets.env
# ===========================================================================


class TestMissingFile:
    def test_resolve_returns_none_when_no_file(self, loader):
        """resolve must return None when secrets.env does not exist and no env var."""
        assert loader.resolve("${OPENAI_API_KEY}") is None

    def test_is_configured_returns_false_when_no_file(self, loader):
        """is_configured must return False when secrets.env does not exist."""
        assert loader.is_configured("${OPENAI_API_KEY}") is False

    def test_remove_key_no_crash_when_no_file(self, loader):
        """remove_key must not crash when secrets.env does not exist."""
        loader.remove_key("${OPENAI_API_KEY}")  # must not raise


# ===========================================================================
# Edge case: Empty file
# ===========================================================================


class TestEmptyFile:
    def test_resolve_returns_none_for_empty_file(self, loader, secrets_file):
        """resolve must return None when secrets.env is empty."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text("")

        assert loader.resolve("${OPENAI_API_KEY}") is None

    def test_is_configured_returns_false_for_empty_file(self, loader, secrets_file):
        """is_configured must return False when secrets.env is empty."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text("")

        assert loader.is_configured("${OPENAI_API_KEY}") is False


# ===========================================================================
# Dotenv format: comments and blank lines
# ===========================================================================


class TestDotenvFormat:
    def test_comments_are_ignored_during_resolve(self, loader, secrets_file):
        """Lines starting with # must be ignored during resolve."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text(
            "# Managed by Runsight\n# OPENAI_API_KEY=sk-commented-out\nANTHROPIC_API_KEY=sk-real\n"
        )

        assert loader.resolve("${OPENAI_API_KEY}") is None
        assert loader.resolve("${ANTHROPIC_API_KEY}") == "sk-real"

    def test_blank_lines_are_ignored(self, loader, secrets_file):
        """Blank lines must not cause errors."""
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text(
            "# Managed by Runsight\n\nOPENAI_API_KEY=sk-abc\n\nANTHROPIC_API_KEY=sk-def\n\n"
        )

        assert loader.resolve("${OPENAI_API_KEY}") == "sk-abc"
        assert loader.resolve("${ANTHROPIC_API_KEY}") == "sk-def"


# ===========================================================================
# AC: Atomic writes
# ===========================================================================


class TestAtomicWrites:
    def test_store_key_uses_atomic_write(self, loader, tmp_path, monkeypatch):
        """store_key must write via temp file + os.rename, not direct write."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        loader.store_key("openai", "sk-abc123")

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"
        runsight_dir = str(tmp_path / ".runsight")
        dst_paths = [dst for _, dst in renames]
        assert any(runsight_dir in str(p) for p in dst_paths), (
            f"Rename destination not in .runsight dir: {dst_paths}"
        )

    def test_remove_key_uses_atomic_write(self, loader, tmp_path, monkeypatch):
        """remove_key must also use atomic writes when the file exists."""
        loader.store_key("openai", "sk-abc123")

        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        loader.remove_key("${OPENAI_API_KEY}")

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"


# ===========================================================================
# Round-trip fidelity
# ===========================================================================


class TestRoundTrip:
    def test_store_then_resolve_round_trip(self, loader):
        """Data must survive a store -> resolve round trip."""
        loader.store_key("openai", "sk-abc123")
        assert loader.resolve("${OPENAI_API_KEY}") == "sk-abc123"

    def test_multiple_providers_round_trip(self, loader):
        """Multiple providers must coexist and round-trip correctly."""
        loader.store_key("openai", "sk-openai")
        loader.store_key("anthropic", "sk-anthropic")
        loader.store_key("azure_openai", "sk-azure")

        assert loader.resolve("${OPENAI_API_KEY}") == "sk-openai"
        assert loader.resolve("${ANTHROPIC_API_KEY}") == "sk-anthropic"
        assert loader.resolve("${AZURE_OPENAI_API_KEY}") == "sk-azure"

    def test_store_remove_store_round_trip(self, loader):
        """Store → remove → re-store must work correctly."""
        loader.store_key("openai", "sk-v1")
        loader.remove_key("${OPENAI_API_KEY}")
        assert loader.resolve("${OPENAI_API_KEY}") is None

        loader.store_key("openai", "sk-v2")
        assert loader.resolve("${OPENAI_API_KEY}") == "sk-v2"
