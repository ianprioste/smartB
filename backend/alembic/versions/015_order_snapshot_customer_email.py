"""Add customer_email to bling_order_snapshots

Revision ID: 015_order_snapshot_customer_email
Revises: 014_bling_product_snapshots
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "015_order_snapshot_customer_email"
down_revision = "014_bling_product_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bling_order_snapshots",
        sa.Column("customer_email", sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_column("bling_order_snapshots", "customer_email")
