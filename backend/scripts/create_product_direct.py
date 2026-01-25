#!/usr/bin/env python3
"""Create and delete a product in Bling using the token stored in DB.

This avoids pytest skip guards by running the integration flow directly.
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


async def run_create_delete(token):
    client = BlingClient(access_token=token.access_token, refresh_token=token.refresh_token)
    sku = f"INT_{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "codigo": sku,
        "nome": f"Integration Test {sku}",
        "tipo": "P",
        "formato": "V",
        "preco": 9.90,
        "situacao": "A",
        "variacoes": [
            {"codigo": f"{sku}-VAR1", "nome": f"{sku} - VAR1", "preco": 9.90, "tipo": "P", "formato": "S", "situacao": "A"}
        ]
    }

    print("Creating product with payload:")
    print(payload)

    resp = await client.post("/produtos", payload)
    print("Create response:", resp)
    created_id = None
    if isinstance(resp, dict):
        created_id = resp.get("data", {}).get("id")

    if created_id:
        print("Created product id:", created_id)
        try:
            await client.delete(f"/produtos/{created_id}")
            print("Deleted product id:", created_id)
        except Exception as e:
            print("Failed to delete product:", e)
    else:
        print("No product id returned; create may have failed.")


def main():
    token = get_token_from_db()
    if not token:
        print("No Bling token in DB; cannot run create test.")
        return 2

    print("Using token (masked):", token.access_token[:8] + "...")
    try:
        asyncio.run(run_create_delete(token))
    except Exception as e:
        print("Error during create/delete:", e)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
