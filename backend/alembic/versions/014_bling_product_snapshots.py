"""Create bling_product_snapshots table.

Revision ID: 014_bling_product_snapshots
Revises: 013_bling_webhook_events
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = "014_bling_product_snapshots"
down_revision = "013_bling_webhook_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("bling_product_snapshots"):
        return

    op.create_table(
        "bling_product_snapshots",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("tenant_id", sa.CHAR(32), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bling_product_id", sa.BigInteger, nullable=False),
        sa.Column("codigo", sa.String(length=255), nullable=True),
        sa.Column("nome", sa.String(length=500), nullable=True),
        sa.Column("formato", sa.String(length=20), nullable=True),
        sa.Column("situacao", sa.String(length=50), nullable=True),
        sa.Column("parent_product_id", sa.BigInteger, nullable=True),
        sa.Column("stock_quantity", sa.Float, nullable=True),
        sa.Column("raw_payload", sa.JSON, nullable=True),
        sa.Column("source_updated_at", sa.DateTime, nullable=True),
        sa.Column("imported_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "bling_product_id", name="uq_bling_product_snapshot_tenant_product"),
    )
    op.create_index("ix_bling_product_snapshots_product", "bling_product_snapshots", ["bling_product_id"])


def downgrade() -> None:
    op.drop_table("bling_product_snapshots")
