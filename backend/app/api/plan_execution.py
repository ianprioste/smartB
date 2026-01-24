"""Plan execution API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from uuid import UUID

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/plans", tags=["Plan Execution"])

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def _get_bling_client(db: Session) -> Optional[BlingClient]:
    """Get authenticated Bling client."""
    token = BlingTokenRepository.get_by_tenant(db, TENANT_ID)
    if not token:
        return None

    async def on_token_refresh(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db, TENANT_ID, access_token, refresh_token, expires_at
        )

    return BlingClient(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_expires_at=token.expires_at,
        on_token_refresh=on_token_refresh,
    )


async def fetch_id_by_sku(client: BlingClient, sku: str) -> Optional[int]:
    """Fetch product ID by SKU from Bling."""
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


def ensure_codigo(payload: Dict[str, Any], sku: str) -> Dict[str, Any]:
    """Ensure codigo field is set."""
    payload = dict(payload or {})
    payload["codigo"] = sku
    return payload


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields that should not be sent in create/update."""
    payload = dict(payload or {})
    payload.pop("id", None)
    payload.pop("variacao", None)
    return payload


def normalize_parent_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize parent product payload for formato V."""
    payload = ensure_codigo(
        sanitize_payload(item.get("computed_payload_preview", {})), item["sku"]
    )
    payload.setdefault("tipo", "P")
    payload["formato"] = "V"
    payload.setdefault("situacao", "A")
    payload.setdefault("nome", f"Produto {item['sku']}")
    payload.setdefault("preco", 0)
    # Do not pop variacoes - they will be added later
    return payload


def extract_parent_and_base(item: Dict[str, Any]):
    """Extract parent and base SKUs from hard dependencies."""
    parent_sku = None
    base_sku = None
    hard = item.get("hard_dependencies") or []
    if len(hard) >= 1:
        parent_sku = hard[0]
    if len(hard) >= 2:
        base_sku = hard[1]
    return parent_sku, base_sku


async def upsert_product(
    client: BlingClient, payload: Dict[str, Any], sku: str
) -> Optional[int]:
    """Create or update product by SKU. Returns product id."""
    existing_id = await fetch_id_by_sku(client, sku)
    if existing_id:
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


async def create_product(client: BlingClient, payload: Dict[str, Any]) -> Optional[int]:
    """Create product directly without checking if exists. Returns product id."""
    resp = await client.post("/produtos", payload)
    if isinstance(resp, dict):
        return resp.get("data", {}).get("id")
    return None


@router.post("/{plan_id}/execute")
async def execute_plan(plan_id: str, db: Session = Depends(get_db)):
    """Execute a plan by creating/updating products in Bling.
    
    For now, accepts plan JSON directly in body as we don't have plan persistence yet.
    """
    # TODO: Load plan from database when persistence is implemented
    # For now, we expect the plan JSON in the request body
    raise HTTPException(
        status_code=501,
        detail="Plan execution endpoint needs plan JSON in request body"
    )


@router.post("/execute")
async def execute_plan_direct(plan: Dict[str, Any], db: Session = Depends(get_db)):
    """Execute a plan directly from JSON payload.
    
    Request body should contain the complete plan with items array.
    """
    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(
            status_code=401,
            detail="Bling token not configured"
        )

    items = plan.get("items", [])
    if not items:
        raise HTTPException(
            status_code=400,
            detail="Plan has no items to execute"
        )

    # Build children map for parent variations
    children_map: Dict[str, list] = {}
    for it in items:
        if it.get("entity") != "VARIATION_PRINTED":
            continue
        parent_sku, base_sku = extract_parent_and_base(it)
        if not parent_sku or not base_sku:
            continue
        base_id = await fetch_id_by_sku(client, base_sku)
        if not base_id:
            logger.warning(f"Base {base_sku} not found for variation {it.get('sku')}")
            continue

        preview = it.get("computed_payload_preview", {})
        produto_nome = preview.get("nome") or it.get("sku")
        variacao_data = preview.get("variacao") or {}
        variacao_nome = variacao_data.get("nome", "")
        sku = it.get("sku", "")
        
        # Generate unique variation name if empty or duplicate
        if not variacao_nome or variacao_nome == "Cor:Branca;Modelo:P":
            variacao_nome = f"SKU:{sku}"
        
        variacao_ordem = variacao_data.get("ordem", 0)

        child = {
            "codigo": sku,
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

    # Track created IDs
    base_ids: Dict[str, int] = {}
    parent_ids: Dict[str, int] = {}
    results = []

    # Process BASE creates
    for item in items:
        if item.get("action") != "CREATE":
            continue
        if not item.get("entity", "").startswith("BASE"):
            continue

        sku = item["sku"]
        payload = ensure_codigo(
            sanitize_payload(item.get("computed_payload_preview", {})), sku
        )
        payload.setdefault("tipo", "P")
        payload.setdefault("formato", payload.get("formato", "S"))

        logger.info(f"Creating base {sku}")
        created_id = await upsert_product(client, payload, sku)
        if created_id:
            base_ids[sku] = created_id
            results.append({"sku": sku, "entity": "BASE", "action": "CREATE", "id": created_id, "status": "success"})
        else:
            results.append({"sku": sku, "entity": "BASE", "action": "CREATE", "status": "failed"})

    # Process PARENT creates with variations
    for item in items:
        if item.get("action") != "CREATE":
            continue
        if item.get("entity") != "PARENT_PRINTED":
            continue

        sku = item["sku"]
        payload = normalize_parent_payload(item)
        payload["variacoes"] = children_map.get(sku, [])
        
        logger.info(f"Creating parent {sku} with {len(payload['variacoes'])} variations")
        created_id = await upsert_product(client, payload, sku)
        if created_id:
            parent_ids[sku] = created_id
            variations_count = len(payload['variacoes'])
            results.append({
                "sku": sku, 
                "entity": "PARENT", 
                "action": "CREATE", 
                "id": created_id, 
                "status": "success",
                "variations_count": variations_count
            })
        else:
            results.append({"sku": sku, "entity": "PARENT", "action": "CREATE", "status": "failed"})

    # Process UPDATEs
    for item in items:
        if item.get("action") != "UPDATE":
            continue

        sku = item["sku"]
        existing = item.get("existing_product") or {}
        prod_id = existing.get("id") or await fetch_id_by_sku(client, sku)
        if not prod_id:
            results.append({"sku": sku, "action": "UPDATE", "status": "failed", "error": "Product not found"})
            continue

        if item.get("entity") == "PARENT_PRINTED":
            payload = normalize_parent_payload(item)
        elif item.get("entity") == "VARIATION_PRINTED":
            parent_sku, base_sku = extract_parent_and_base(item)
            parent_id = parent_ids.get(parent_sku) or await fetch_id_by_sku(client, parent_sku)
            base_id = base_ids.get(base_sku) or await fetch_id_by_sku(client, base_sku)
            if not parent_id or not base_id:
                results.append({"sku": sku, "action": "UPDATE", "status": "failed", "error": "Missing parent or base"})
                continue
            # Build composition payload for variation update
            payload = ensure_codigo(item.get("computed_payload_preview", {}), sku)
        else:
            payload = ensure_codigo(item.get("computed_payload_preview", {}), sku)

        logger.info(f"Updating {sku} (id {prod_id})")
        try:
            resp = await client.put(f"/produtos/{prod_id}", payload)
            results.append({"sku": sku, "action": "UPDATE", "id": prod_id, "status": "success"})
        except Exception as e:
            results.append({"sku": sku, "action": "UPDATE", "id": prod_id, "status": "failed", "error": str(e)})

    await client.client.aclose()
    
    success_results = [r for r in results if r.get("status") == "success"]
    created_parents = [r for r in success_results if r.get("entity") == "PARENT" and r.get("action") == "CREATE"]
    total_variations = sum(r.get("variations_count", 0) for r in created_parents)

    return {
        "status": "completed",
        "total_items": len(items),
        "results": results,
        "summary": {
            "created_bases": len([r for r in results if r.get("entity") == "BASE" and r.get("status") == "success"]),
            "created_parents": len(created_parents),
            "created_variations": total_variations,
            "updated": len([r for r in results if r.get("action") == "UPDATE" and r.get("status") == "success"]),
            "failed": len([r for r in results if r.get("status") == "failed"]),
        }
    }


@router.post("/seed-bases")
async def seed_missing_bases(plan: Dict[str, Any], db: Session = Depends(get_db)):
    """Create missing base products (plain, unprinted items)."""
    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling token not configured")

    seed_summary = plan.get("seed_summary", {})
    if not seed_summary:
        raise HTTPException(status_code=400, detail="No seed_summary in plan")

    try:
        results = []
        base_parent_skus = seed_summary.get("base_parent_missing", [])
        base_variation_skus = seed_summary.get("base_variation_missing", [])
        
        logger.info(f"Creating {len(base_parent_skus)} base parents with {len(base_variation_skus)} variations")
        logger.info(f"Creating {len(base_parent_skus)} base parents with {len(base_variation_skus)} variations")
        
        # Create each base parent with its variations
        for parent_sku in base_parent_skus:
            variations = [v for v in base_variation_skus if v.startswith(parent_sku) and v != parent_sku]
            
            if not variations:
                # Simple product without variations
                payload = {
                    "codigo": parent_sku,
                    "nome": f"Base {parent_sku}",
                    "tipo": "P",
                    "formato": "S",
                    "situacao": "A",
                    "preco": 0
                }
            else:
                # Parent with variations
                variacoes = []
                for var_sku in variations:
                    color = var_sku.replace(parent_sku, "")
                    variacoes.append({
                        "codigo": var_sku,
                        "nome": f"Base {var_sku}",
                        "preco": 0,
                        "tipo": "P",
                        "formato": "S",
                        "situacao": "A",
                        "variacao": {"nome": f"Cor:{color}", "ordem": len(variacoes)}
                    })
                
                payload = {
                    "codigo": parent_sku,
                    "nome": f"Base {parent_sku}",
                    "tipo": "P",
                    "formato": "V",
                    "situacao": "A",
                    "preco": 0,
                    "variacoes": variacoes
                }
            
            created_id = await create_product(client, payload)
            if created_id:
                results.append({
                    "sku": parent_sku, 
                    "id": created_id, 
                    "status": "created",
                    "variations_count": len(variations) if variations else 0
                })
                logger.info(f"✓ Created base {parent_sku} (id: {created_id})")
            else:
                results.append({"sku": parent_sku, "status": "failed"})
                logger.error(f"✗ Failed to create base {parent_sku}")
        
        await client.client.aclose()
        
        success_results = [r for r in results if r["status"] == "created"]
        total_variations = sum(r.get("variations_count", 0) for r in success_results)
        
        return {
            "results": results,
            "summary": {
                "created_products": len(success_results),
                "created_variations": total_variations,
                "total_items": len(success_results) + total_variations
            }
        }
    
    except BlingRefreshTokenExpiredError:
        logger.error("Bling token expired")
        raise HTTPException(status_code=401, detail={
            "code": "BLING_TOKEN_EXPIRED",
            "message": "Token expirado"
        })
    except Exception as e:
        logger.error(f"Error creating bases: {e}")
        raise HTTPException(status_code=500, detail=str(e))
