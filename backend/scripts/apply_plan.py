#!/usr/bin/env python3
"""Apply a generated plan_result.json to Bling.

Steps:
1) Create missing base products (BASE_* entities) when present in the plan.
2) Create parent printed products (PARENT_PRINTED) as "formato V".
3) Create variation printed products (VARIATION_PRINTED) as compositions (formato E)
   referencing the base product as a component and linking to the parent via idProdutoPai.
4) Update products with action UPDATE (parents and variations), preserving composition links.

Usage:
  python scripts/apply_plan.py path/to/plan_result.json

The script uses the token stored in DB (tenant 000...001) like the other helper scripts.
"""
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

repo_root = Path(__file__).resolve().parents[2]
backend_dir = repo_root / "backend"
sys.path.insert(0, str(backend_dir))

from app.infra.db import SessionLocal
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient

FIXED_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def get_token_from_db():
    db = SessionLocal()
    try:
        return BlingTokenRepository.get_by_tenant(db, FIXED_TENANT_ID)
    finally:
        db.close()


async def fetch_id_by_sku(client: BlingClient, sku: str) -> Optional[int]:
    resp = await client.get(
        "/produtos",
        params={"codigos[]": [sku], "tipo": "T", "limite": 1},
    )
    data = resp.get("data") if isinstance(resp, dict) else None
    if not data:
        return None
    for item in data:
        if item.get("codigo") == sku:
            return item.get("id")
    return None


async def upsert_product(client: BlingClient, payload: Dict[str, Any], sku: str) -> Optional[int]:
    """Create or update by SKU. Returns product id."""
    existing_id = await fetch_id_by_sku(client, sku)
    if existing_id:
        # For formato V, Bling requires variations; to avoid validation error, force POST as new composition flow
        # If PUT fails we will fall back to POST below
        try:
            resp = await client.put(f"/produtos/{existing_id}", payload)
            if isinstance(resp, dict):
                return resp.get("data", {}).get("id", existing_id) or existing_id
            return existing_id
        except Exception:
            pass
    resp = await client.post("/produtos", payload)
    if isinstance(resp, dict):
        return resp.get("data", {}).get("id")
    return None


def ensure_codigo(payload: Dict[str, Any], sku: str) -> Dict[str, Any]:
    payload = dict(payload or {})
    payload["codigo"] = sku
    return payload


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove ids and variation fields that force PUT behavior."""
    payload = dict(payload or {})
    payload.pop("id", None)
    payload.pop("variacao", None)
    return payload


def normalize_parent_payload(item: Dict[str, Any], existing_product: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build parent payload, preserving existing product data (especially images/links).
    
    Strategy: Start with existing product and only update specific fields.
    """
    preview = item.get("computed_payload_preview", {})
    sku = item["sku"]
    
    # When updating, start with existing product to preserve ALL metadata
    if existing_product:
        payload = dict(existing_product)  # Copy all existing fields
    else:
        payload = ensure_codigo(sanitize_payload(preview), sku)
    
    # Update these specific fields
    payload["codigo"] = sku
    payload["tipo"] = "P"
    payload["formato"] = "V"
    
    # Only update if provided in preview (don't override if not provided)
    if "nome" in preview:
        payload["nome"] = preview["nome"]
    if "descricaoCurta" in preview:
        payload["descricaoCurta"] = preview.get("descricaoCurta", "")
    if "descricaoComplementar" in preview:
        payload["descricaoComplementar"] = preview.get("descricaoComplementar", "")
    if "preco" in preview:
        payload["preco"] = preview.get("preco", 0)
    
    # Remove fields that should not be in update payload
    payload.pop("id", None)
    payload.pop("dataCriacao", None)
    payload.pop("dataAlteracao", None)
    payload.pop("variacoes", None)  # Will be set separately
    
    return payload


def build_composition_payload(item: Dict[str, Any], parent_id: int, base_id: int) -> Dict[str, Any]:
    preview = item.get("computed_payload_preview", {})
    payload = ensure_codigo(sanitize_payload(preview), item["sku"])
    payload.setdefault("tipo", "P")
    payload["formato"] = "E"  # composition
    payload.setdefault("preco", 0)
    payload.setdefault("situacao", "A")
    # Link as variation to parent with cloneInfo false
    variacao_nome = (
        (preview.get("variacao") or {}).get("nome")
        or preview.get("nome")
        or item["sku"]
    )
    payload["variacao"] = {
        "nome": variacao_nome,
        "ordem": (preview.get("variacao") or {}).get("ordem", 0),
        "produtoPai": {"id": parent_id, "cloneInfo": False},
    }
    # Also include idProdutoPai for completeness
    payload["idProdutoPai"] = parent_id
    estrutura = {
        "componentes": [
            {"produto": {"id": base_id}, "quantidade": 1},
        ],
        "tipoEstoque": "V",
        "lancamentoEstoque": "A",
    }
    payload["estrutura"] = estrutura
    return payload


def extract_parent_and_base(item: Dict[str, Any]):
    parent_sku = None
    base_sku = None
    hard = item.get("hard_dependencies") or []
    # Expected order from plan builder: [parent_sku, base_sku]
    if len(hard) >= 1:
        parent_sku = hard[0]
    if len(hard) >= 2:
        base_sku = hard[1]
    return parent_sku, base_sku


async def main(argv):
    plan_path = Path(argv[1]) if len(argv) > 1 else Path("plan_result.json")
    if not plan_path.exists():
        print(f"Plan file not found: {plan_path}")
        return 2

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    items = plan.get("items", [])

    token = get_token_from_db()
    if not token:
        print("No Bling token in DB; cannot run apply.")
        return 2

    client = BlingClient(access_token=token.access_token, refresh_token=token.refresh_token)

    # Build mapping: parent_sku -> list of child variation composition payloads
    children_map: Dict[str, list] = {}
    for it in items:
        if it.get("entity") != "VARIATION_PRINTED":
            continue
        parent_sku, base_sku = extract_parent_and_base(it)
        if not parent_sku or not base_sku:
            continue
        base_id = await fetch_id_by_sku(client, base_sku)
        if not base_id:
            print(f"[PARENT VAR MAP] base id not found for {base_sku}; skipping child {it.get('sku')}")
            continue
        preview = it.get("computed_payload_preview", {})
        # Use the full product name from preview (parent title + variations)
        produto_nome = preview.get("nome") or it.get("sku")
        
        # Extract variation specification from preview
        variacao_data = preview.get("variacao") or {}
        variacao_nome = variacao_data.get("nome", "")
        
        # If variation name is empty or all same, use SKU to generate unique variation
        sku = it.get("sku", "")
        if not variacao_nome or variacao_nome == "Cor:Branca;Modelo:P":
            # Use the full SKU as variation identifier to ensure uniqueness
            variacao_nome = f"SKU:{sku}"
        
        variacao_ordem = variacao_data.get("ordem", 0)
        
        child = {
            "codigo": it.get("sku"),
            "nome": produto_nome,
            "preco": preview.get("preco") or 0,
            "tipo": "P",
            "formato": "E",
            "situacao": "A",
            "variacao": {
                "nome": variacao_nome,
                "ordem": variacao_ordem,
            },
            "estrutura": {
                "componentes": [{"produto": {"id": base_id}, "quantidade": 1}],
                "tipoEstoque": "V",
                "lancamentoEstoque": "A",
            },
        }
        children_map.setdefault(parent_sku, []).append(child)

    # Maps for IDs
    base_ids: Dict[str, int] = {}
    parent_ids: Dict[str, int] = {}

    # Process BASE_* creates first
    for item in items:
        if item.get("action") != "CREATE":
            continue
        if not item.get("entity", "").startswith("BASE"):
            continue

        sku = item["sku"]
        payload = ensure_codigo(sanitize_payload(item.get("computed_payload_preview", {})), sku)
        payload.setdefault("tipo", "P")
        payload.setdefault("formato", payload.get("formato", "S"))

        print(f"[BASE CREATE] {sku}")
        created_id = await upsert_product(client, payload, sku)
        if created_id:
            base_ids[sku] = created_id
            print(f"  -> upsert id {created_id}")
        else:
            print(f"  -> upsert failed (no id)")

    # Process PARENT creates (formato V with variacoes - Bling creates all children automatically)
    for item in items:
        if item.get("action") != "CREATE":
            continue
        if item.get("entity") != "PARENT_PRINTED":
            continue

        sku = item["sku"]
        payload = normalize_parent_payload(item)
        # Include all child variations - Bling will create them atomically
        payload["variacoes"] = children_map.get(sku, [])
        print(f"[PARENT+CHILDREN CREATE] {sku} with {len(payload['variacoes'])} variations")
        created_id = await upsert_product(client, payload, sku)
        if created_id:
            parent_ids[sku] = created_id
            print(f"  -> upsert id {created_id}")
        else:
            print(f"  -> upsert failed (no id)")

    # Skip individual VARIATION creates - they were created automatically with parent
    # (Children are already created by Bling when parent is created with variacoes[])
    print(f"[VAR CREATE] Skipping individual child creation - already created with parent")

    # Process UPDATEs (parents and variations)
    for item in items:
        if item.get("action") != "UPDATE":
            continue

        sku = item["sku"]
        existing = item.get("existing_product") or {}
        prod_id = existing.get("id") or await fetch_id_by_sku(client, sku)
        if not prod_id:
            print(f"[UPDATE] {sku} -> id not found; skipping")
            continue

        if item.get("entity") == "PARENT_PRINTED":
            # Fetch full existing product to preserve images
            try:
                existing_full = await client.get(f"/produtos/{prod_id}")
                existing_product_data = existing_full.get("data", {}) if isinstance(existing_full, dict) else existing
            except Exception as e:
                print(f"[UPDATE] {sku} -> warning: could not fetch existing product: {e}")
                existing_product_data = existing
            
            payload = normalize_parent_payload(item, existing_product_data)
            # Do NOT include variacoes on update - children maintain their own linkage
        elif item.get("entity") == "VARIATION_PRINTED":
            parent_sku, base_sku = extract_parent_and_base(item)
            parent_id = parent_ids.get(parent_sku) or await fetch_id_by_sku(client, parent_sku)
            base_id = base_ids.get(base_sku) or await fetch_id_by_sku(client, base_sku)
            if not parent_id or not base_id:
                print(f"[UPDATE] {sku} -> missing parent/base ids; skipping")
                continue
            payload = build_composition_payload(item, parent_id, base_id)
        else:
            payload = ensure_codigo(item.get("computed_payload_preview", {}), sku)

        print(f"[UPDATE] {sku} -> id {prod_id}")
        resp = await client.put(f"/produtos/{prod_id}", payload)
        if isinstance(resp, dict):
            print(f"  -> status: {resp.get('status', 'OK')}")
        else:
            print(f"  -> response: {resp}")

    await client.client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv)))
