"""Add NEW_PLAIN plan type and product_kind to product snapshots.

Revision ID: 017_plan_type_new_plain_and_product_kind
Revises: 016_order_snapshot_customer_contact_id
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "017_plan_type_new_plain_and_product_kind"
down_revision = "016_order_snapshot_customer_contact_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("ALTER TYPE plantypeenum ADD VALUE IF NOT EXISTS 'NEW_PLAIN';")
        op.execute(
            """
            DO $$ BEGIN
                CREATE TYPE productkindenum AS ENUM ('PLAIN', 'PRINTED');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """
        )

    snapshot_columns = {col["name"] for col in inspector.get_columns("bling_product_snapshots")}
    if "product_kind" not in snapshot_columns:
        if dialect == "postgresql":
            product_kind_enum = sa.Enum("PLAIN", "PRINTED", name="productkindenum", create_type=False)
            op.add_column("bling_product_snapshots", sa.Column("product_kind", product_kind_enum, nullable=True))
        else:
            op.add_column("bling_product_snapshots", sa.Column("product_kind", sa.String(length=20), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    snapshot_columns = {col["name"] for col in inspector.get_columns("bling_product_snapshots")}
    if "product_kind" in snapshot_columns:
        op.drop_column("bling_product_snapshots", "product_kind")

    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS productkindenum;")