"""Add is_active field to sales_events table for campaign status

Revision ID: 009_sales_event_is_active
Revises: 008_parent_child_status_sync
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa


revision = "009_sales_event_is_active"
down_revision = "008_parent_child_status_sync"
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

    # Add is_active column to track campaign status (active/inactive)
    if not _column_exists(conn, "sales_events", "is_active"):
        op.add_column(
            "sales_events",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove is_active column
    if _column_exists(conn, "sales_events", "is_active"):
        op.drop_column("sales_events", "is_active")
