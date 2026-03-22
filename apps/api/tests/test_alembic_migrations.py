"""Red tests for RUN-255: Introduce Alembic for SQLite schema migrations.

Replace `SQLModel.metadata.create_all(engine)` in `main.py` with proper
Alembic migrations.  These tests verify the structural/file-level
requirements from the acceptance criteria using file existence checks and
source inspection — no runtime Alembic execution needed.

Every test should FAIL until the implementation is written.
"""

import pathlib
import re


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Root of the runsight_api package on disk
_PKG_ROOT = pathlib.Path(__file__).resolve().parent.parent / "src" / "runsight_api"

_ALEMBIC_DIR = _PKG_ROOT / "alembic"
_ALEMBIC_INI = _PKG_ROOT / "alembic.ini"
_ENV_PY = _ALEMBIC_DIR / "env.py"
_SCRIPT_MAKO = _ALEMBIC_DIR / "script.py.mako"
_VERSIONS_DIR = _ALEMBIC_DIR / "versions"
_MAIN_PY = _PKG_ROOT / "main.py"


# ---------------------------------------------------------------------------
# Alembic directory structure
# ---------------------------------------------------------------------------


class TestAlembicDirectoryStructure:
    """Verify the Alembic scaffolding files exist."""

    def test_alembic_ini_exists(self):
        """alembic.ini must exist at the package root."""
        assert _ALEMBIC_INI.is_file(), f"Expected alembic.ini at {_ALEMBIC_INI}"

    def test_alembic_env_py_exists(self):
        """alembic/env.py must exist."""
        assert _ENV_PY.is_file(), f"Expected env.py at {_ENV_PY}"

    def test_alembic_script_mako_exists(self):
        """alembic/script.py.mako template must exist."""
        assert _SCRIPT_MAKO.is_file(), f"Expected script.py.mako at {_SCRIPT_MAKO}"

    def test_versions_directory_exists(self):
        """alembic/versions/ directory must exist."""
        assert _VERSIONS_DIR.is_dir(), f"Expected versions directory at {_VERSIONS_DIR}"


# ---------------------------------------------------------------------------
# env.py content
# ---------------------------------------------------------------------------


class TestAlembicEnvPy:
    """Verify that env.py is configured correctly for SQLite + SQLModel."""

    def test_render_as_batch_enabled(self):
        """env.py must contain render_as_batch=True for SQLite ALTER support."""
        content = _ENV_PY.read_text()
        assert "render_as_batch=True" in content, (
            "env.py must include render_as_batch=True for SQLite compatibility"
        )

    def test_target_metadata_uses_sqlmodel(self):
        """env.py must set target_metadata to SQLModel.metadata."""
        content = _ENV_PY.read_text()
        assert "target_metadata" in content, "env.py must define target_metadata"
        # Accept both `target_metadata = SQLModel.metadata`
        # and `target_metadata=SQLModel.metadata`
        assert re.search(r"target_metadata\s*=\s*SQLModel\.metadata", content), (
            "env.py must set target_metadata = SQLModel.metadata"
        )


# ---------------------------------------------------------------------------
# Initial migration
# ---------------------------------------------------------------------------


class TestInitialMigration:
    """At least one migration file must exist in alembic/versions/."""

    def test_at_least_one_migration_exists(self):
        """versions/ must contain at least one .py migration file."""
        assert _VERSIONS_DIR.is_dir(), f"versions directory missing: {_VERSIONS_DIR}"
        migration_files = list(_VERSIONS_DIR.glob("*.py"))
        assert len(migration_files) >= 1, (
            f"Expected at least one migration file in {_VERSIONS_DIR}, found none"
        )

    def test_migration_contains_upgrade_function(self):
        """The migration file must define an upgrade() function."""
        assert _VERSIONS_DIR.is_dir(), f"versions directory missing: {_VERSIONS_DIR}"
        migration_files = list(_VERSIONS_DIR.glob("*.py"))
        assert migration_files, "No migration files found"

        # Check the first migration file for an upgrade function
        content = migration_files[0].read_text()
        assert "def upgrade(" in content, "Migration file must contain a def upgrade() function"

    def test_migration_contains_downgrade_function(self):
        """The migration file must define a downgrade() function."""
        assert _VERSIONS_DIR.is_dir(), f"versions directory missing: {_VERSIONS_DIR}"
        migration_files = list(_VERSIONS_DIR.glob("*.py"))
        assert migration_files, "No migration files found"

        content = migration_files[0].read_text()
        assert "def downgrade(" in content, "Migration file must contain a def downgrade() function"


# ---------------------------------------------------------------------------
# main.py — create_all removed, alembic used instead
# ---------------------------------------------------------------------------


class TestMainPyMigration:
    """main.py must no longer use create_all and should use Alembic instead."""

    def test_create_all_removed_from_main(self):
        """main.py must NOT call SQLModel.metadata.create_all."""
        content = _MAIN_PY.read_text()
        assert "create_all" not in content, (
            "main.py still contains 'create_all' — it should use Alembic migrations instead"
        )

    def test_main_references_alembic(self):
        """main.py must import or call alembic (e.g., alembic.command or alembic.config)."""
        content = _MAIN_PY.read_text()
        assert "alembic" in content, (
            "main.py does not reference 'alembic' — "
            "it should import alembic.command or alembic.config to run migrations"
        )
