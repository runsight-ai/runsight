"""Add run.warnings_json snapshot column.

Revision ID: 002_add_run_warnings_json
Revises: 001_initial
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_run_warnings_json"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _run_has_warnings_json() -> bool:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("run")}
    return "warnings_json" in columns


def upgrade() -> None:
    """Add nullable warnings snapshot column to run table."""
    if _run_has_warnings_json():
        return

    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("warnings_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop warnings snapshot column from run table."""
    if not _run_has_warnings_json():
        return

    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("warnings_json")
