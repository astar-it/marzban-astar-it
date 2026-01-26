"""add connection_limit

Revision ID: a1b2c3d4e5f6
Revises: 07f9bbb3db4e
Create Date: 2026-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '07f9bbb3db4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add connection_limit column to users table
    op.add_column('users', sa.Column('connection_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'connection_limit')
