"""Add order tags tables

Revision ID: 011_order_tags_and_links
Revises: 010_password_reset_codes
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


revision = "011_order_tags_and_links"
down_revision = "010_password_reset_codes"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    indexes = inspector.get_indexes(table_name)
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade() -> None:
    conn = op.get_bind()
    uuid_type = PG_UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(length=32)

    if not _table_exists(conn, "order_tags"):
        op.create_table(
            "order_tags",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("scope_key", sa.String(length=255), nullable=False),
            sa.Column("event_id", uuid_type, sa.ForeignKey("sales_events.id"), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("name_key", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "scope_key", "event_id", "name_key", name="uq_order_tags_tenant_scope_event_name_key"),
        )

    if not _index_exists(conn, "order_tags", "ix_order_tags_scope"):
        op.create_index("ix_order_tags_scope", "order_tags", ["tenant_id", "scope_key", "event_id"], unique=False)

    if not _table_exists(conn, "order_tag_links"):
        op.create_table(
            "order_tag_links",
            sa.Column("id", uuid_type, primary_key=True),
            sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("scope_key", sa.String(length=255), nullable=False),
            sa.Column("event_id", uuid_type, sa.ForeignKey("sales_events.id"), nullable=True),
            sa.Column("bling_order_id", sa.BigInteger(), nullable=False),
            sa.Column("tag_id", uuid_type, sa.ForeignKey("order_tags.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "scope_key", "event_id", "bling_order_id", "tag_id", name="uq_order_tag_links_tenant_scope_event_order_tag"),
        )

    if not _index_exists(conn, "order_tag_links", "ix_order_tag_links_lookup"):
        op.create_index(
            "ix_order_tag_links_lookup",
            "order_tag_links",
            ["tenant_id", "scope_key", "event_id", "bling_order_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _table_exists(conn, "order_tag_links"):
        if _index_exists(conn, "order_tag_links", "ix_order_tag_links_lookup"):
            op.drop_index("ix_order_tag_links_lookup", table_name="order_tag_links")
        op.drop_table("order_tag_links")

    if _table_exists(conn, "order_tags"):
        if _index_exists(conn, "order_tags", "ix_order_tags_scope"):
            op.drop_index("ix_order_tags_scope", table_name="order_tags")
        op.drop_table("order_tags")
