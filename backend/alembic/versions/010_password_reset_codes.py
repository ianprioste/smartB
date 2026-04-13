"""Add password reset codes table

Revision ID: 010_password_reset_codes
Revises: 009_sales_event_is_active
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


revision = "010_password_reset_codes"
down_revision = "009_sales_event_is_active"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def upgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "password_reset_codes"):
        return

    uuid_type = UUID(as_uuid=True) if conn.dialect.name == "postgresql" else sa.CHAR(length=32)

    op.create_table(
        "password_reset_codes",
        sa.Column("id", uuid_type, primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", uuid_type, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("access_users.id"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_password_reset_codes_user_id", "password_reset_codes", ["user_id"], unique=False)
    op.create_index("ix_password_reset_codes_email", "password_reset_codes", ["email"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "password_reset_codes"):
        return

    op.drop_index("ix_password_reset_codes_email", table_name="password_reset_codes")
    op.drop_index("ix_password_reset_codes_user_id", table_name="password_reset_codes")
    op.drop_table("password_reset_codes")
