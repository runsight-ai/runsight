"""
Red-phase tests for RUN-237: Remove SQLite provider/settings tables and encryption module.

These tests verify that all cleanup actions have been completed:
- Deleted files no longer exist on disk
- No stale imports reference deleted modules
- api_key_encrypted references are fully removed
- cryptography dependency is removed from pyproject.toml
- SQLite tables for Run, RunNode, LogEntry remain functional
- _migrate_schema function is removed from main.py
- SQLModel table classes (Provider, AppSettings, FallbackChain, ModelDefault) are removed
- Pydantic models (AppSettingsConfig, FallbackTargetEntry, ModelDefaultEntry) are preserved
- repositories/__init__.py no longer exports deleted repos
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[3]  # apps/api
_SRC = _ROOT / "src" / "runsight_api"
_PYPROJECT = _ROOT / "pyproject.toml"


# =========================================================================
# AC1 / AC5: Deleted files must not exist
# =========================================================================


class TestDeletedFiles:
    """Files that must be removed from the repo."""

    def test_encryption_module_deleted(self):
        path = _SRC / "core" / "encryption.py"
        assert not path.exists(), f"encryption.py should be deleted: {path}"

    def test_sqlite_provider_repo_deleted(self):
        path = _SRC / "data" / "repositories" / "provider_repo.py"
        assert not path.exists(), f"SQLite provider_repo.py should be deleted: {path}"

    def test_sqlite_settings_repo_deleted(self):
        path = _SRC / "data" / "repositories" / "settings_repo.py"
        assert not path.exists(), f"SQLite settings_repo.py should be deleted: {path}"


# =========================================================================
# AC1 / AC5: No stale imports of deleted modules in source code
# =========================================================================


def _python_source_files() -> list[Path]:
    """Return all .py files under apps/api/src/."""
    return sorted(_SRC.rglob("*.py"))


class TestNoStaleImports:
    """No source file should reference deleted modules."""

    def test_no_encryption_imports(self):
        """AC5: grep -r 'from.*encryption import' apps/api/ returns zero results."""
        hits: list[str] = []
        for py in _python_source_files():
            text = py.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"from\s+\S*encryption\s+import", line):
                    hits.append(f"{py}:{i}: {line.strip()}")
        assert hits == [], "Source files still import from encryption module:\n" + "\n".join(hits)

    def test_no_provider_repository_import(self):
        """No source file should import ProviderRepository from repositories."""
        pattern = re.compile(
            r"from\s+\S*data\.repositories\.provider_repo\s+import|"
            r"from\s+\S*data\.repositories\s+import\s+.*ProviderRepository"
        )
        hits: list[str] = []
        for py in _python_source_files():
            text = py.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{py}:{i}: {line.strip()}")
        assert hits == [], "Source files still import SQLite ProviderRepository:\n" + "\n".join(
            hits
        )

    def test_no_settings_repository_import(self):
        """No source file should import SettingsRepository from repositories."""
        pattern = re.compile(
            r"from\s+\S*data\.repositories\.settings_repo\s+import|"
            r"from\s+\S*data\.repositories\s+import\s+.*SettingsRepository"
        )
        hits: list[str] = []
        for py in _python_source_files():
            text = py.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{py}:{i}: {line.strip()}")
        assert hits == [], "Source files still import SQLite SettingsRepository:\n" + "\n".join(
            hits
        )


# =========================================================================
# AC4: No api_key_encrypted references
# =========================================================================


class TestNoApiKeyEncrypted:
    """AC4: grep -r 'api_key_encrypted' apps/api/ returns zero results."""

    def test_no_api_key_encrypted_in_source(self):
        hits: list[str] = []
        for py in _python_source_files():
            text = py.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if "api_key_encrypted" in line:
                    hits.append(f"{py}:{i}: {line.strip()}")
        assert hits == [], "api_key_encrypted still referenced in source:\n" + "\n".join(hits)


# =========================================================================
# AC2: cryptography removed from pyproject.toml
# =========================================================================


class TestCryptographyDependency:
    """AC2: cryptography package removed from dependencies."""

    def test_cryptography_not_in_pyproject(self):
        text = _PYPROJECT.read_text()
        assert "cryptography" not in text, (
            "pyproject.toml still lists 'cryptography' as a dependency"
        )


# =========================================================================
# SQLModel Provider class removed from domain/entities/provider.py
# =========================================================================


class TestProviderEntityCleaned:
    """Provider(SQLModel, table=True) must be removed."""

    def test_no_sqlmodel_provider_class(self):
        provider_file = _SRC / "domain" / "entities" / "provider.py"
        if not provider_file.exists():
            # File deleted entirely is also acceptable
            return
        text = provider_file.read_text()
        assert "class Provider(SQLModel, table=True)" not in text, (
            "domain/entities/provider.py still contains SQLModel Provider class"
        )

    def test_no_sqlmodel_import_in_provider(self):
        provider_file = _SRC / "domain" / "entities" / "provider.py"
        if not provider_file.exists():
            return
        text = provider_file.read_text()
        assert "from sqlmodel" not in text, "domain/entities/provider.py still imports sqlmodel"


# =========================================================================
# SQLModel settings classes removed from domain/entities/settings.py
# =========================================================================


class TestSettingsEntityCleaned:
    """SQLModel table classes removed; Pydantic models preserved."""

    def test_no_sqlmodel_app_settings_class(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        assert settings_file.exists(), "settings.py should still exist (has Pydantic models)"
        text = settings_file.read_text()
        assert "class AppSettings(SQLModel, table=True)" not in text, (
            "settings.py still contains SQLModel AppSettings class"
        )

    def test_no_sqlmodel_fallback_chain_class(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class FallbackChain(SQLModel, table=True)" not in text, (
            "settings.py still contains SQLModel FallbackChain class"
        )

    def test_no_sqlmodel_model_default_class(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class ModelDefault(SQLModel, table=True)" not in text, (
            "settings.py still contains SQLModel ModelDefault class"
        )

    def test_pydantic_app_settings_config_preserved(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class AppSettingsConfig(BaseModel)" in text, (
            "settings.py should still contain Pydantic AppSettingsConfig"
        )

    def test_pydantic_fallback_chain_entry_removed(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class FallbackChainEntry(BaseModel)" not in text, (
            "settings.py should no longer contain Pydantic FallbackChainEntry"
        )

    def test_pydantic_fallback_target_entry_preserved(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class FallbackTargetEntry(BaseModel)" in text, (
            "settings.py should still contain Pydantic FallbackTargetEntry"
        )

    def test_pydantic_model_default_entry_preserved(self):
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "class ModelDefaultEntry(BaseModel)" in text, (
            "settings.py should still contain Pydantic ModelDefaultEntry"
        )

    def test_no_sqlmodel_import_in_settings(self):
        """After removing SQLModel classes, sqlmodel import should be gone."""
        settings_file = _SRC / "domain" / "entities" / "settings.py"
        text = settings_file.read_text()
        assert "from sqlmodel" not in text, "settings.py still imports sqlmodel after cleanup"


# =========================================================================
# _migrate_schema removed from main.py
# =========================================================================


class TestMainCleaned:
    """_migrate_schema function and related imports removed from main.py."""

    def test_no_migrate_schema_function(self):
        main_file = _SRC / "main.py"
        text = main_file.read_text()
        assert "_migrate_schema" not in text, (
            "main.py still contains _migrate_schema function or call"
        )

    def test_no_provider_repo_import_in_main(self):
        main_file = _SRC / "main.py"
        text = main_file.read_text()
        assert "ProviderRepository" not in text, "main.py still imports ProviderRepository"
        assert "from .data.repositories.provider_repo" not in text, (
            "main.py still imports from SQLite provider_repo"
        )


# =========================================================================
# repositories/__init__.py cleaned
# =========================================================================


class TestRepositoriesInitCleaned:
    """__init__.py should only export RunRepository."""

    def test_no_provider_repository_export(self):
        init_file = _SRC / "data" / "repositories" / "__init__.py"
        text = init_file.read_text()
        assert "ProviderRepository" not in text, (
            "repositories/__init__.py still exports ProviderRepository"
        )

    def test_no_settings_repository_export(self):
        init_file = _SRC / "data" / "repositories" / "__init__.py"
        text = init_file.read_text()
        assert "SettingsRepository" not in text, (
            "repositories/__init__.py still exports SettingsRepository"
        )

    def test_run_repository_still_exported(self):
        init_file = _SRC / "data" / "repositories" / "__init__.py"
        text = init_file.read_text()
        assert "RunRepository" in text, "repositories/__init__.py must still export RunRepository"


# =========================================================================
# AC3: SQLite DB still works for Run, RunNode, LogEntry
# =========================================================================


class TestSqliteTablesPreserved:
    """Run, RunNode, LogEntry SQLModel classes and RunRepository must still work."""

    def test_run_entity_importable(self):
        from runsight_api.domain.entities.run import Run, RunNode

        assert hasattr(Run, "__tablename__")
        assert hasattr(RunNode, "__tablename__")

    def test_log_entry_importable(self):
        from runsight_api.domain.entities.log import LogEntry

        assert hasattr(LogEntry, "__tablename__")

    def test_run_repository_importable(self):
        from runsight_api.data.repositories.run_repo import RunRepository

        assert RunRepository is not None

    def test_run_repository_in_init(self):
        from runsight_api.data.repositories import RunRepository

        assert RunRepository is not None


# =========================================================================
# Filesystem repos preserved
# =========================================================================


class TestFilesystemReposPreserved:
    """Filesystem-backed repos must NOT be deleted."""

    def test_filesystem_provider_repo_exists(self):
        path = _SRC / "data" / "filesystem" / "provider_repo.py"
        assert path.exists(), f"Filesystem provider_repo.py must be preserved: {path}"

    def test_filesystem_settings_repo_exists(self):
        path = _SRC / "data" / "filesystem" / "settings_repo.py"
        assert path.exists(), f"Filesystem settings_repo.py must be preserved: {path}"
