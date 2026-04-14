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

        required_run_columns = ["parent_run_id", "parent_node_id", "root_run_id", "depth"]
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


class TestAlembicMigrationAddsRunWarningsJson:
    """A migration must add and drop run.warnings_json for non-SQLite DBs."""

    def test_migration_file_adds_and_drops_warnings_json(self) -> None:
        """The Alembic versions directory should contain a migration for warnings_json."""
        versions_dir = (
            Path(__file__).resolve().parents[2] / "src" / "runsight_api" / "alembic" / "versions"
        )
        migration_sources = [
            path.read_text() for path in versions_dir.glob("*.py") if path.name != "__init__.py"
        ]

        assert migration_sources, f"No Alembic migrations found in {versions_dir}"
        assert any("warnings_json" in source for source in migration_sources), (
            "Expected an Alembic migration that mentions warnings_json"
        )
        assert any(
            "add_column" in source and "warnings_json" in source for source in migration_sources
        ), "Expected an Alembic upgrade path that adds warnings_json"
        assert any(
            "drop_column" in source and "warnings_json" in source for source in migration_sources
        ), "Expected an Alembic downgrade path that drops warnings_json"
