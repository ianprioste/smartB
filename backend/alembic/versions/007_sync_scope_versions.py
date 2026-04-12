"""Add SQL-based sync scope versions for delta polling

Revision ID: 007_sync_scope_versions
Revises: 006_access_password
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa
import uuid


revision = "007_sync_scope_versions"
down_revision = "006_access_password"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def _index_exists(conn, index_name: str) -> bool:
    inspector = sa.inspect(conn)
    if not inspector.has_table("sync_scope_versions"):
        return False
    for idx in inspector.get_indexes("sync_scope_versions"):
        if idx.get("name") == index_name:
            return True
    return False


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "sync_scope_versions"):
        op.create_table(
            "sync_scope_versions",
            sa.Column("id", sa.String(length=36), primary_key=True, default=lambda: str(uuid.uuid4())),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("scope_key", sa.String(length=255), nullable=False),
            sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "scope_key", name="uq_sync_scope_versions_tenant_scope"),
        )

    if not _index_exists(conn, "ix_sync_scope_versions_tenant_scope"):
        op.create_index(
            "ix_sync_scope_versions_tenant_scope",
            "sync_scope_versions",
            ["tenant_id", "scope_key"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "ix_sync_scope_versions_tenant_scope"):
        op.drop_index("ix_sync_scope_versions_tenant_scope", table_name="sync_scope_versions")
    if _table_exists(conn, "sync_scope_versions"):
        op.drop_table("sync_scope_versions")
