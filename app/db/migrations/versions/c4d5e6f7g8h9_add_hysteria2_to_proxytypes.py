"""add hysteria2 to proxytypes

Revision ID: c4d5e6f7g8h9
Revises: a1b2c3d4e5f6
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7g8h9'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE proxytypes ADD VALUE IF NOT EXISTS 'hysteria2'")
    elif dialect == 'mysql':
        op.execute(
            "ALTER TABLE proxies MODIFY COLUMN type "
            "ENUM('vmess','vless','trojan','shadowsocks','hysteria2') NOT NULL"
        )
    # SQLite uses text for enums, no alteration needed


def downgrade() -> None:
    pass
