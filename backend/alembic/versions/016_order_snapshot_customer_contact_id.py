"""Add customer_contact_id to bling_order_snapshots.

Revision ID: 016_order_snapshot_customer_contact_id
Revises: 015_order_snapshot_customer_email
Create Date: 2026-04-16
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "016_order_snapshot_customer_contact_id"
down_revision = "015_order_snapshot_customer_email"
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


def _try_int(value):
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _extract_contact_id(raw_order, raw_detail):
    for payload in (raw_detail, raw_order):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue

        contato = data.get("contato") if isinstance(data.get("contato"), dict) else {}
        candidates = [
            contato.get("id"),
            data.get("idContato"),
            data.get("contatoId"),
        ]
        for candidate in candidates:
            contact_id = _try_int(candidate)
            if contact_id is not None:
                return contact_id

    return None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("bling_order_snapshots")}
    if "customer_contact_id" not in columns:
        op.add_column(
            "bling_order_snapshots",
            sa.Column("customer_contact_id", sa.BigInteger(), nullable=True),
        )

    rows = conn.execute(sa.text("SELECT id, raw_order, raw_detail FROM bling_order_snapshots")).fetchall()
    for row_id, raw_order_value, raw_detail_value in rows:
        raw_order = _payload_to_dict(raw_order_value)
        raw_detail = _payload_to_dict(raw_detail_value)
        contact_id = _extract_contact_id(raw_order, raw_detail)
        if contact_id is None:
            continue

        conn.execute(
            sa.text("UPDATE bling_order_snapshots SET customer_contact_id = :contact_id WHERE id = :row_id"),
            {"contact_id": contact_id, "row_id": row_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("bling_order_snapshots")}
    if "customer_contact_id" not in columns:
        return

    op.drop_column("bling_order_snapshots", "customer_contact_id")
