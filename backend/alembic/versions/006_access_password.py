"""Add password_hash to access_users; create access tables if missing

Revision ID: 006_access_password
Revises: 005_bling_order_snapshots
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


revision = "006_access_password"
down_revision = "005_bling_order_snapshots"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return result.scalar()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c)"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # Create access_profiles if it doesn't exist yet (may have been created via create_all)
    if not _table_exists(conn, "access_profiles"):
        op.create_table(
            "access_profiles",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "name", name="uq_access_profiles_tenant_name"),
        )

    # Create access_users if it doesn't exist yet
    if not _table_exists(conn, "access_users"):
        op.create_table(
            "access_users",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("access_profiles.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "email", name="uq_access_users_tenant_email"),
        )
    else:
        # Table exists — add the column if it doesn't exist yet
        if not _column_exists(conn, "access_users", "password_hash"):
            op.add_column("access_users", sa.Column("password_hash", sa.String(length=255), nullable=True))

    # Create access_sessions if it doesn't exist yet
    if not _table_exists(conn, "access_sessions"):
        op.create_table(
            "access_sessions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("access_users.id"), nullable=False),
            sa.Column("token", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("token", name="uq_access_sessions_token"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "access_users", "password_hash"):
        op.drop_column("access_users", "password_hash")
