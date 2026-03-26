"""Add sales events tables

Revision ID: 004_sales_events
Revises: 003_sprint3_plans
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = "004_sales_events"
down_revision = "003_sprint3_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sales_event_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("sales_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bling_product_id", sa.BigInteger(), nullable=True),
        sa.Column("sku", sa.String(length=255), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "sku", name="uq_sales_event_products_event_sku"),
    )

    op.create_index("ix_sales_events_tenant", "sales_events", ["tenant_id"])
    op.create_index("ix_sales_events_period", "sales_events", ["start_date", "end_date"])
    op.create_index("ix_sales_event_products_event", "sales_event_products", ["event_id"])
    op.create_index("ix_sales_event_products_sku", "sales_event_products", ["sku"])


def downgrade() -> None:
    op.drop_index("ix_sales_event_products_sku", table_name="sales_event_products")
    op.drop_index("ix_sales_event_products_event", table_name="sales_event_products")
    op.drop_index("ix_sales_events_period", table_name="sales_events")
    op.drop_index("ix_sales_events_tenant", table_name="sales_events")
    op.drop_table("sales_event_products")
    op.drop_table("sales_events")
