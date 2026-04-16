"""Add customer_email to bling_order_snapshots.

Revision ID: 015_order_snapshot_customer_email
Revises: 014_bling_product_snapshots
Create Date: 2026-04-16
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "015_order_snapshot_customer_email"
down_revision = "014_bling_product_snapshots"
branch_labels = None
depends_on = None


def _payload_to_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _extract_email(raw_order, raw_detail):
    for payload in (raw_detail, raw_order):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue

        contato = data.get("contato") if isinstance(data.get("contato"), dict) else {}
        cliente = data.get("cliente") if isinstance(data.get("cliente"), dict) else {}
        candidates = [
            contato.get("email"),
            cliente.get("email"),
            data.get("email"),
            data.get("emailContato"),
        ]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and "@" in text:
                return text

    return None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("bling_order_snapshots")}
    if "customer_email" in columns:
        return

    op.add_column(
        "bling_order_snapshots",
        sa.Column("customer_email", sa.String(length=500), nullable=True),
    )

    rows = conn.execute(sa.text("SELECT id, raw_order, raw_detail FROM bling_order_snapshots")).fetchall()
    for row_id, raw_order_value, raw_detail_value in rows:
        raw_order = _payload_to_dict(raw_order_value)
        raw_detail = _payload_to_dict(raw_detail_value)
        email = _extract_email(raw_order, raw_detail)
        if not email:
            continue

        conn.execute(
            sa.text("UPDATE bling_order_snapshots SET customer_email = :email WHERE id = :row_id"),
            {"email": email, "row_id": row_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("bling_order_snapshots")}
    if "customer_email" not in columns:
        return

    op.drop_column("bling_order_snapshots", "customer_email")