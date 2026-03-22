"""Initial schema — baseline migration.

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-22
"""

from typing import Sequence, Union

from alembic import op
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from SQLModel metadata."""
    bind = op.get_bind()
    sqlmodel.SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    """Drop all tables from SQLModel metadata."""
    bind = op.get_bind()
    sqlmodel.SQLModel.metadata.drop_all(bind)
