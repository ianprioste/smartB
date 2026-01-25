#!/usr/bin/env python3
"""Create a child product as a composition including SKU CAMBRP as component.

Usage:
  python scripts/create_child_composition.py [parent_sku]

If parent_sku provided, the new composition will reference it as idProdutoPai when possible.
"""
import sys
import asyncio
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
backend_dir = repo_root / 'backend'
import os
sys.path.insert(0, str(backend_dir))

from app.infra.db import SessionLocal
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient
import uuid

CAMBRP_SKU = "CAMBRP"


def get_token_from_db():
    db = SessionLocal()
    try:
        FIXED_TENANT_ID = "00000000-0000-0000-0000-000000000001"
        token = BlingTokenRepository.get_by_tenant(db, FIXED_TENANT_ID)
        return token
    finally:
        db.close()


async def create_composition(parent_sku: str | None = None):
    token = get_token_from_db()
    if not token:
        print("No Bling token in DB; cannot run creation.")
        return 2

    client = BlingClient(access_token=token.access_token, refresh_token=token.refresh_token)

    # lookup CAMBRP and optional parent
    skus = [CAMBRP_SKU]
    if parent_sku:
        skus.append(parent_sku)
    produtos = await client.get_produtos_by_skus(skus)

    cambrp = produtos.get(CAMBRP_SKU)
    if not cambrp or not cambrp.get("id"):
        print("CAMBRP not found in Bling:", cambrp)
        return 1
    cambrp_id = cambrp.get("id")

    parent_id = None
    if parent_sku:
        p = produtos.get(parent_sku)
        parent_id = p.get("id") if p and p.get("id") else None

    suffix = uuid.uuid4().hex[:8].upper()
    child_sku = f"filho_comp_{suffix}"

    payload = {
        "codigo": child_sku,
        "nome": f"Filho Compo {child_sku}",
        "tipo": "P",
        "formato": "E",
        "preco": 0,
        "situacao": "A",
        "estrutura": {
            "componentes": [
                {"produto": {"id": cambrp_id}, "quantidade": 1}
            ],
            "tipoEstoque": "F",
            "lancamentoEstoque": "A",
        }
    }

    # If parent exists, include idProdutoPai in payload
    if parent_id:
        payload["idProdutoPai"] = parent_id

    print("Creating composition product with payload:")
    print(payload)

    try:
        resp = await client.post("/produtos", payload)
        print("Create response:", resp)
        created_id = None
        if isinstance(resp, dict):
            created_id = resp.get("data", {}).get("id")
        if created_id:
            print("Created composition product id:", created_id)
            return 0
        else:
            print("No id returned; response:", resp)
            return 1
    except Exception as e:
        print("Failed to create composition:", e)
        return 1


def main(argv):
    parent_sku = argv[1] if len(argv) > 1 else None
    return asyncio.run(create_composition(parent_sku))


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
