"""Add persistent Bling order snapshots and sync state

Revision ID: 005_bling_order_snapshots
Revises: 004_sales_events
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = "005_bling_order_snapshots"
down_revision = "004_sales_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bling_order_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bling_order_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.BigInteger(), nullable=True),
        sa.Column("numero_loja", sa.String(length=255), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=True),
        sa.Column("customer_name", sa.String(length=500), nullable=True),
        sa.Column("status_id", sa.Integer(), nullable=True),
        sa.Column("status_name", sa.String(length=255), nullable=True),
        sa.Column("total_value", sa.Float(), nullable=True),
        sa.Column("raw_order", sa.JSON(), nullable=True),
        sa.Column("raw_detail", sa.JSON(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "bling_order_id", name="uq_bling_order_snapshot_tenant_order"),
    )

    op.create_table(
        "bling_orders_sync_state",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("last_full_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_incremental_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_status", sa.String(length=50), nullable=True),
        sa.Column("last_sync_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", name="uq_bling_orders_sync_state_tenant"),
    )

    op.create_index("ix_bling_order_snapshots_tenant", "bling_order_snapshots", ["tenant_id"])
    op.create_index("ix_bling_order_snapshots_order_date", "bling_order_snapshots", ["order_date"])
    op.create_index("ix_bling_order_snapshots_status", "bling_order_snapshots", ["status_id"])


def downgrade() -> None:
    op.drop_index("ix_bling_order_snapshots_status", table_name="bling_order_snapshots")
    op.drop_index("ix_bling_order_snapshots_order_date", table_name="bling_order_snapshots")
    op.drop_index("ix_bling_order_snapshots_tenant", table_name="bling_order_snapshots")
    op.drop_table("bling_orders_sync_state")
    op.drop_table("bling_order_snapshots")