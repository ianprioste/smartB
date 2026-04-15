"""Create bling_webhook_events table for event idempotency and retry tracking.

Revision ID: 013_bling_webhook_events
Revises: 012_order_tags_legacy_columns_fix
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa


revision = "013_bling_webhook_events"
down_revision = "012_order_tags_legacy_columns_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("bling_webhook_events"):
        return

    op.create_table(
        "bling_webhook_events",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("tenant_id", sa.CHAR(32), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("bling_order_id", sa.BigInteger, nullable=True),
        sa.Column("raw_payload", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum("received", "processing", "processed", "failed", "dead", name="blingwebhookeventstatusenum"),
            nullable=False,
            server_default="received",
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("received_at", sa.DateTime, nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_bling_webhook_events_tenant_idempotency"),
    )
    op.create_index("ix_bling_webhook_events_status", "bling_webhook_events", ["status"])
    op.create_index("ix_bling_webhook_events_bling_order_id", "bling_webhook_events", ["bling_order_id"])


def downgrade() -> None:
    op.drop_table("bling_webhook_events")
