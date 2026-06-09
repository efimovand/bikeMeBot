"""add payment table

Revision ID: d7e3b9a51c20
Revises: 24cec50b676d
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e3b9a51c20'
down_revision: Union[str, Sequence[str], None] = '24cec50b676d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'payment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_tg_id', sa.BigInteger(), nullable=False),
        sa.Column('charge_id', sa.String(length=255), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('generations', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('charge_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('payment')
