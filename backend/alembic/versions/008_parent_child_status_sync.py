"""Add parent-child status sync fields for item production notes

Revision ID: 008_parent_child_status_sync
Revises: 007_sync_scope_versions
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa


revision = "008_parent_child_status_sync"
down_revision = "007_sync_scope_versions"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    for col in inspector.get_columns(table_name):
        if col.get("name") == column_name:
            return True
    return False


def upgrade() -> None:
    conn = op.get_bind()

    # Add parent_sku column for tracking parent-child relationships
    if not _column_exists(conn, "item_production_notes", "parent_sku"):
        op.add_column(
            "item_production_notes",
            sa.Column("parent_sku", sa.String(length=255), nullable=True)
        )

    # Add is_parent column to mark if item is a parent product
    if not _column_exists(conn, "item_production_notes", "is_parent"):
        op.add_column(
            "item_production_notes",
            sa.Column("is_parent", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove is_parent column
    if _column_exists(conn, "item_production_notes", "is_parent"):
        op.drop_column("item_production_notes", "is_parent")

    # Remove parent_sku column
    if _column_exists(conn, "item_production_notes", "parent_sku"):
        op.drop_column("item_production_notes", "parent_sku")
