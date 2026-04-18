"""
RUN-663 — Failing tests for RunNode.exit_handle field and SQLite backfill columns.
RUN-842 — Failing tests for Run.warnings_json backfill coverage and migration.

These tests verify:
  3. RunNode has an ``exit_handle`` field (currently missing)
  4. SQLite backfill dict covers the new nested-run columns
  5. SQLite backfill dict covers Run.warnings_json
  6. An Alembic migration adds/drops run.warnings_json

Tests MUST fail because:
  - RunNode does not have ``exit_handle`` field
  - _ensure_sqlite_columns does not include parent_run_id, parent_node_id,
    root_run_id, depth on ``run`` table
  - _ensure_sqlite_columns does not include child_run_id, exit_handle on
    ``runnode`` table
  - _ensure_sqlite_columns does not include warnings_json on ``run`` table
  - there is no Alembic migration that adds/drops warnings_json yet
"""

from __future__ import annotations

import re
from pathlib import Path

from runsight_api.domain.entities.run import RunNode


# ---------------------------------------------------------------------------
# 3h-i: RunNode exit_handle field
# ---------------------------------------------------------------------------


class TestRunNodeExitHandle:
    """RunNode entity must have an exit_handle field."""

    def test_run_node_has_exit_handle_field(self) -> None:
        """(h) RunNode must expose an exit_handle attribute."""
        node = RunNode(
            id="run1:block1",
            run_id="run1",
            node_id="block1",
            block_type="WorkflowBlock",
        )
        assert hasattr(node, "exit_handle"), "RunNode must have an 'exit_handle' field"

    def test_run_node_exit_handle_persists_round_trip(self, tmp_path) -> None:
        """(i) Create RunNode with exit_handle='completed', save to DB, reload,
        assert value is preserved."""
        from sqlmodel import Session, SQLModel, create_engine, select

        db_path = tmp_path / "test_run663.db"
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)

        # Create and persist
        node = RunNode(
            id="run1:block1",
            run_id="run1",
            node_id="block1",
            block_type="WorkflowBlock",
            exit_handle="completed",
        )
        with Session(engine) as session:
            session.add(node)
            session.commit()

        # Reload and verify
        with Session(engine) as session:
            loaded = session.exec(select(RunNode).where(RunNode.id == "run1:block1")).one()
            assert loaded.exit_handle == "completed", (
                f"exit_handle must round-trip through DB, got '{loaded.exit_handle}'"
            )


# ---------------------------------------------------------------------------
# 4j-k: SQLite backfill columns
# ---------------------------------------------------------------------------


class TestSqliteBackfillColumns:
    """_ensure_sqlite_columns must cover nested-run fields."""

    def test_ensure_sqlite_columns_includes_run_parent_fields(self) -> None:
        """(j) Backfill dict must cover parent_run_id, parent_node_id,
        root_run_id, depth on the 'run' table."""
        import inspect

        from runsight_api.main import _ensure_sqlite_columns

        source = inspect.getsource(_ensure_sqlite_columns)

        required_run_columns = [
            "parent_run_id",
            "parent_node_id",
            "root_run_id",
            "depth",
            "deleted_at",
        ]
        for col in required_run_columns:
            assert col in source, (
                f"_ensure_sqlite_columns must include '{col}' in the 'run' table backfill dict"
            )

    def test_ensure_sqlite_columns_includes_runnode_child_fields(self) -> None:
        """(k) Backfill dict must cover child_run_id, exit_handle on the
        'runnode' table."""
        import inspect

        from runsight_api.main import _ensure_sqlite_columns

        source = inspect.getsource(_ensure_sqlite_columns)

        required_runnode_columns = ["child_run_id", "exit_handle"]
        for col in required_runnode_columns:
            assert col in source, (
                f"_ensure_sqlite_columns must include '{col}' in the 'runnode' table backfill dict"
            )

    def test_ensure_sqlite_columns_includes_run_warnings_json(self) -> None:
        """(l) Backfill dict must cover warnings_json on the 'run' table."""
        import inspect

        from runsight_api.main import _ensure_sqlite_columns

        source = inspect.getsource(_ensure_sqlite_columns)
        assert "warnings_json" in source, (
            "_ensure_sqlite_columns must include 'warnings_json' in the 'run' table backfill dict"
        )

    def test_ensure_sqlite_columns_backfills_warnings_json_on_legacy_run_table(
        self, tmp_path
    ) -> None:
        """Backfill must execute and add run.warnings_json on legacy SQLite tables."""
        from sqlalchemy import create_engine

        from runsight_api.main import _ensure_sqlite_columns

        db_path = tmp_path / "run663_legacy.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE run (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    task_json TEXT NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE runnode (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    block_type TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )

        _ensure_sqlite_columns(engine)

        with engine.begin() as conn:
            run_columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(run)").fetchall()
            }
            assert "warnings_json" in run_columns, (
                "Expected _ensure_sqlite_columns to add warnings_json to legacy run table"
            )


class TestAlembicMigrationAddsRunWarningsJson:
    """A migration must add and drop run.warnings_json for non-SQLite DBs."""

    def test_migration_file_adds_and_drops_warnings_json(self) -> None:
        """Migration after 001_initial must batch-alter run and add/drop warnings_json."""
        versions_dir = (
            Path(__file__).resolve().parents[2] / "src" / "runsight_api" / "alembic" / "versions"
        )
        version_files = sorted(
            path for path in versions_dir.glob("*.py") if path.name != "__init__.py"
        )
        assert version_files, f"No Alembic migrations found in {versions_dir}"

        follow_up_revisions = [path for path in version_files if "001_initial" not in path.stem]
        assert follow_up_revisions, "Expected at least one migration file after 001_initial"

        target_migrations: list[tuple[Path, str]] = []
        for path in follow_up_revisions:
            source = path.read_text()
            if re.search(r'down_revision\s*[:=][^"\']*["\']001_initial["\']', source):
                target_migrations.append((path, source))

        assert target_migrations, "Expected a migration with down_revision = '001_initial'"

        warning_migrations = [
            (path, source) for path, source in target_migrations if "warnings_json" in source
        ]
        assert warning_migrations, "Expected migration after 001_initial to reference warnings_json"

        for path, source in warning_migrations:
            assert 'batch_alter_table("run")' in source or "batch_alter_table('run')" in source, (
                f"{path.name} must use batch_alter_table('run') for SQLite compatibility"
            )
            upgrade_body = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
            assert "warnings_json" in upgrade_body and "add_column" in upgrade_body, (
                f"{path.name} upgrade() must add run.warnings_json"
            )
            assert "nullable=True" in upgrade_body, (
                f"{path.name} upgrade() must add warnings_json as nullable"
            )
            assert "JSON" in upgrade_body, (
                f"{path.name} upgrade() must use a JSON column type for warnings_json"
            )

            downgrade_body = source.split("def downgrade", 1)[1]
            assert "warnings_json" in downgrade_body and "drop_column" in downgrade_body, (
                f"{path.name} downgrade() must drop run.warnings_json"
            )
