"""add server default to assessments id column

Revision ID: fe55456a8940
Revises: 6ac40cae8f1a
Create Date: 2026-05-10 12:01:01.405365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'fe55456a8940'
down_revision: Union[str, Sequence[str], None] = '6ac40cae8f1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the schema changes for this revision."""
    op.alter_column(
        'assessments',
        'id',
        server_default=sa.text('gen_random_uuid()'),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Revert the schema changes for this revision."""
    op.alter_column(
        'assessments',
        'id',
        server_default=None,
    )
    # ### end Alembic commands ###
