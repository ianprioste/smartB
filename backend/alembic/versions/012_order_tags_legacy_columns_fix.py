"""Fix legacy order tag tables missing columns.

Revision ID: 012_order_tags_legacy_columns_fix
Revises: 011_order_tags_and_links
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa


revision = "012_order_tags_legacy_columns_fix"
down_revision = "011_order_tags_and_links"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "order_tags"):
        if not _column_exists(conn, "order_tags", "name_key"):
            op.add_column("order_tags", sa.Column("name_key", sa.String(length=80), nullable=True))
        if not _column_exists(conn, "order_tags", "created_at"):
            op.add_column("order_tags", sa.Column("created_at", sa.DateTime(), nullable=True))
        if not _column_exists(conn, "order_tags", "updated_at"):
            op.add_column("order_tags", sa.Column("updated_at", sa.DateTime(), nullable=True))

    if _table_exists(conn, "order_tag_links"):
        if not _column_exists(conn, "order_tag_links", "created_at"):
            op.add_column("order_tag_links", sa.Column("created_at", sa.DateTime(), nullable=True))
        if not _column_exists(conn, "order_tag_links", "updated_at"):
            op.add_column("order_tag_links", sa.Column("updated_at", sa.DateTime(), nullable=True))

    if _table_exists(conn, "order_tag_assignments"):
        if not _column_exists(conn, "order_tag_assignments", "created_at"):
            op.add_column("order_tag_assignments", sa.Column("created_at", sa.DateTime(), nullable=True))
        if not _column_exists(conn, "order_tag_assignments", "updated_at"):
            op.add_column("order_tag_assignments", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Intentionally noop: this migration only repairs legacy drift.
    pass
