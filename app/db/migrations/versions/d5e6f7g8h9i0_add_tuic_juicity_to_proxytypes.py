"""add tuic and juicity to proxytypes

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op


revision = 'd5e6f7g8h9i0'
down_revision = 'c4d5e6f7g8h9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute("ALTER TYPE proxytypes ADD VALUE IF NOT EXISTS 'tuic'")
        op.execute("ALTER TYPE proxytypes ADD VALUE IF NOT EXISTS 'juicity'")
    elif dialect == 'mysql':
        op.execute(
            "ALTER TABLE proxies MODIFY COLUMN type "
            "ENUM('vmess','vless','trojan','shadowsocks','hysteria2','tuic','juicity') NOT NULL"
        )
    # SQLite uses text for enums, no alteration needed


def downgrade() -> None:
    pass
