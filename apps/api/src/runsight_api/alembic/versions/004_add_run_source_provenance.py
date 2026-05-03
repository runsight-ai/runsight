"""Add run source provenance columns.

Revision ID: 004_add_run_source_provenance
Revises: 003_add_run_workflow_input_snapshots
Create Date: 2026-04-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_run_source_provenance"
down_revision: Union[str, None] = "003_add_run_workflow_input_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _run_columns() -> set[str]:
    bind = op.get_bind()
    return {column["name"] for column in sa.inspect(bind).get_columns("run")}


def _run_index_names() -> set[str]:
    bind = op.get_bind()
    return {index["name"] for index in sa.inspect(bind).get_indexes("run")}


def upgrade() -> None:
    """Add nullable source provenance fields and lookup indexes."""
    existing_columns = _run_columns()
    with op.batch_alter_table("run") as batch_op:
        if "source_correlation_id" not in existing_columns:
            batch_op.add_column(sa.Column("source_correlation_id", sa.String(), nullable=True))
        if "source_metadata" not in existing_columns:
            batch_op.add_column(sa.Column("source_metadata", sa.JSON(), nullable=True))

    existing_indexes = _run_index_names()
    if "ix_run_source_created_at" not in existing_indexes:
        op.create_index("ix_run_source_created_at", "run", ["source", "created_at"])
    if "ix_run_workflow_source_created_at" not in existing_indexes:
        op.create_index(
            "ix_run_workflow_source_created_at",
            "run",
            ["workflow_id", "source", "created_at"],
        )


def downgrade() -> None:
    """Remove source provenance fields and lookup indexes."""
    existing_indexes = _run_index_names()
    if "ix_run_workflow_source_created_at" in existing_indexes:
        op.drop_index("ix_run_workflow_source_created_at", table_name="run")
    if "ix_run_source_created_at" in existing_indexes:
        op.drop_index("ix_run_source_created_at", table_name="run")

    existing_columns = _run_columns()
    with op.batch_alter_table("run") as batch_op:
        if "source_metadata" in existing_columns:
            batch_op.drop_column("source_metadata")
        if "source_correlation_id" in existing_columns:
            batch_op.drop_column("source_correlation_id")
