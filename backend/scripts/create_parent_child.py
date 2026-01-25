#!/usr/bin/env python3
"""Create a parent product (pai) with a child (filho) variation using DB token.

Usage:
  python scripts/create_parent_child.py

Will create SKUs like `pai_<8hex>` and `filho_<8hex>` to avoid collisions.
"""
import os
import sys
import asyncio
import uuid
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
backend_dir = repo_root / 'backend'
sys.path.insert(0, str(backend_dir))

from app.infra.db import SessionLocal
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient


def get_token_from_db():
    db = SessionLocal()
    try:
        FIXED_TENANT_ID = "00000000-0000-0000-0000-000000000001"
        token = BlingTokenRepository.get_by_tenant(db, FIXED_TENANT_ID)
        return token
    finally:
        db.close()


async def run_create(token, parent_sku, child_sku):
    client = BlingClient(access_token=token.access_token, refresh_token=token.refresh_token)

    payload = {
        "codigo": parent_sku,
        "nome": f"Pai {parent_sku}",
        "tipo": "P",
        "formato": "V",
        "preco": 19.90,
        "situacao": "A",
        "variacoes": [
            {"codigo": child_sku, "nome": f"Filho {child_sku}", "preco": 19.90, "tipo": "P", "formato": "S", "situacao": "A"}
        ]
    }

    print("Creating parent product with payload:")
    print(payload)

    resp = await client.post("/produtos", payload)
    print("Create response:", resp)
    created_id = None
    if isinstance(resp, dict):
        created_id = resp.get("data", {}).get("id")

    if created_id:
        print("Created parent product id:", created_id)
    else:
        print("No parent id returned; create may have failed.")


def main():
    token = get_token_from_db()
    if not token:
        print("No Bling token in DB; cannot run create.")
        return 2

    suffix = uuid.uuid4().hex[:8].upper()
    parent_sku = f"pai_{suffix}"
    child_sku = f"filho_{suffix}"

    print("Using token (masked):", token.access_token[:8] + "...")
    try:
        asyncio.run(run_create(token, parent_sku, child_sku))
    except Exception as e:
        print("Error during create:", e)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
