"""Add run workflow input snapshot columns.

Revision ID: 003_add_run_workflow_input_snapshots
Revises: 002_add_run_warnings_json
Create Date: 2026-04-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_run_workflow_input_snapshots"
down_revision: Union[str, None] = "002_add_run_warnings_json"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _run_columns() -> set[str]:
    bind = op.get_bind()
    return {column["name"] for column in sa.inspect(bind).get_columns("run")}


def upgrade() -> None:
    """Add nullable workflow input snapshot columns to run table."""
    existing = _run_columns()
    with op.batch_alter_table("run") as batch_op:
        if "workflow_inputs" not in existing:
            batch_op.add_column(sa.Column("workflow_inputs", sa.JSON(), nullable=True))
        if "workflow_input_schema" not in existing:
            batch_op.add_column(sa.Column("workflow_input_schema", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop workflow input snapshot columns from run table."""
    existing = _run_columns()
    with op.batch_alter_table("run") as batch_op:
        if "workflow_input_schema" in existing:
            batch_op.drop_column("workflow_input_schema")
        if "workflow_inputs" in existing:
            batch_op.drop_column("workflow_inputs")
