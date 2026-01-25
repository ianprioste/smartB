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


async def find_parent_sku(client: BlingClient, variation_sku: str) -> Optional[str]:
    """Find parent SKU by progressively removing characters from variation SKU."""
    # Try removing characters from the end until we find an existing product
    for i in range(2, len(variation_sku) - 1):
        potential_parent = variation_sku[:-i]
        existing_id = await fetch_id_by_sku(client, potential_parent)
        if existing_id:
            return potential_parent
    return None


def parse_variation_codes(var_sku: str, parent_sku: str) -> Dict[str, str]:
    """Extract color and size from a variation SKU using the parent SKU as prefix.

    Base SKU format: {MODEL}{COLOR}{SIZE}
    Examples:
      CAMBRP  -> color=BR, size=P
      CAMBRGG -> color=BR, size=GG
      CAMBRXG -> color=BR, size=XG
    """
    suffix = var_sku[len(parent_sku):] if var_sku.startswith(parent_sku) else ""
    size_codes = ["XG", "GG", "G", "M", "P"]  # order matters (longest first)
    size = ""
    for code in size_codes:
        if suffix.endswith(code):
            size = code
            break
    color = suffix[:-len(size)] if size else suffix
    return {"color": color, "size": size}


async def fetch_id_by_sku(client: BlingClient, sku: str) -> Optional[int]:
    """Fetch product ID by SKU from Bling."""
    try:
        resp = await client.get(
            "/produtos",
            params={"codigos[]": sku, "tipo": "T", "limite": 1},
        )
        data = resp.get("data") if isinstance(resp, dict) else None
        if not data:
            return None
        for item in data:
            if item.get("codigo") == sku:
                return item.get("id")
        return None
    except Exception as e:
        logger.error(f"Error fetching product by SKU {sku}: {e}")
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
    try:
        resp = await client.post("/produtos", payload)
        if isinstance(resp, dict):
            product_id = resp.get("data", {}).get("id")
            if product_id:
                return product_id
        logger.error(f"Create product failed - unexpected response: {resp}")
        return None
    except Exception as e:
        logger.error(f"Error creating product: {e}")
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
    print("=" * 80)
    print("SEED-BASES ENDPOINT CALLED")
    print("=" * 80)
    
    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling token not configured")

    seed_summary = plan.get("seed_summary", {})
    print(f"SEED SUMMARY: {seed_summary}")
    if not seed_summary:
        raise HTTPException(status_code=400, detail="No seed_summary in plan")

    try:
        results = []
        base_parent_skus = seed_summary.get("base_parent_missing", [])
        base_variation_skus = seed_summary.get("base_variation_missing", [])
        
        print(f"PARENTS MISSING: {base_parent_skus}")
        print(f"VARIATIONS MISSING: {base_variation_skus}")
        
        # Build model and color lists from plan (ground truth for parent & variation parsing)
        raw_models = plan.get("models", []) or []
        model_codes = [m.get("code", "").upper() for m in raw_models if isinstance(m, dict) and m.get("code")]
        raw_colors = plan.get("colors", []) or []
        color_codes = []
        for c in raw_colors:
            if isinstance(c, dict) and c.get("code"):
                color_codes.append(c.get("code").upper())
            elif isinstance(c, str):
                color_codes.append(c.upper())
        print(f"MODELS FROM PLAN: {model_codes}")
        print(f"COLORS FROM PLAN: {color_codes}")
        
        # Group variations by parent = model code
        parent_to_variations: Dict[str, list] = {}
        
        size_codes = ["XG", "GG", "G", "M", "P"]  # order matters
        for var_sku in base_variation_skus:
            print(f"\nFinding parent for variation: {var_sku}")
            parent_sku = None

            # 1) Try direct match with model list
            for model_code in model_codes:
                if var_sku.startswith(model_code):
                    parent_sku = model_code
                    break

            # 2) If not found, parse using size + color lists
            if not parent_sku:
                suffix_size = ""
                for s in size_codes:
                    if var_sku.endswith(s):
                        suffix_size = s
                        break
                if suffix_size:
                    prefix_without_size = var_sku[: -len(suffix_size)]
                    matched_color = ""
                    for c in color_codes:
                        if prefix_without_size.endswith(c):
                            matched_color = c
                            break
                    if matched_color:
                        parent_sku = prefix_without_size[: -len(matched_color)]
                        print(f"  -> Parsed parent {parent_sku} from color/size (color={matched_color}, size={suffix_size})")

            # 3) Fallback assuming color length 2
            if not parent_sku:
                for s in size_codes:
                    if var_sku.endswith(s) and len(var_sku) > len(s) + 2:
                        parent_sku = var_sku[: -(len(s) + 2)]
                        print(f"  -> Fallback parent {parent_sku} (color length 2, size={s})")
                        break

            if parent_sku:
                parent_to_variations.setdefault(parent_sku, []).append(var_sku)
            else:
                print(f"  -> No parent found for {var_sku}, skipping")
        
        # Ensure parents from base_parent_missing are present even if no variations
        for parent_sku in base_parent_skus:
            parent_to_variations.setdefault(parent_sku, [])
        
        print(f"\nGROUPED BY PARENT: {parent_to_variations}")
        print(f"Total parents to process: {len(parent_to_variations)}")
        if not parent_to_variations:
            logger.warn("seed_bases_no_parents_found", variations=len(base_variation_skus))
            return {
                "results": [],
                "summary": {
                    "created_products": 0,
                    "updated_products": 0,
                    "created_variations": 0,
                    "total_items": 0
                }
            }
        
        logger.info("seed_bases_start", 
                   parents=len(parent_to_variations), 
                   variations=len(base_variation_skus))
        
        # Process each parent with its variations
        for parent_sku, variations in parent_to_variations.items():
            print(f"\n>>> Processing parent: {parent_sku}")
            print(f"    Found {len(variations)} variations: {variations}")
            
            # Check if parent already exists
            existing_id = await fetch_id_by_sku(client, parent_sku)
            print(f"    Existing ID: {existing_id}")
            
            if not variations:
                # Simple product without variations
                if existing_id:
                    logger.info(f"Parent {parent_sku} already exists (id: {existing_id}), skipping")
                    results.append({
                        "sku": parent_sku, 
                        "id": existing_id, 
                        "status": "skipped",
                        "message": "Already exists"
                    })
                    continue
                
                payload = {
                    "codigo": parent_sku,
                    "nome": f"Base {parent_sku}",
                    "tipo": "P",
                    "formato": "S",
                    "situacao": "A",
                    "preco": 0
                }
                
                created_id = await create_product(client, payload)
                if created_id:
                    results.append({
                        "sku": parent_sku, 
                        "id": created_id, 
                        "status": "created",
                        "variations_count": 0
                    })
                    logger.info(f"✓ Created simple base {parent_sku} (id: {created_id})")
                else:
                    results.append({"sku": parent_sku, "status": "failed"})
                    logger.error(f"✗ Failed to create base {parent_sku}")
            else:
                # Parent with variations
                if existing_id:
                    # Get existing product to merge variations
                    logger.info(f"Parent {parent_sku} exists (id: {existing_id}), fetching existing data")
                    try:
                        existing_product = await client.get(f"/produtos/{existing_id}")
                        existing_data = existing_product.get("data", {})
                        existing_variations = existing_data.get("variacoes", [])
                        existing_var_skus = {v.get("codigo") for v in existing_variations if v.get("codigo")}
                        
                        logger.info(f"Existing variations for {parent_sku}: {existing_var_skus}")
                        
                        # Build new variations list (keep existing + add new)
                        variacoes = list(existing_variations)  # Start with existing
                        for var_sku in variations:
                            if var_sku not in existing_var_skus:
                                codes = parse_variation_codes(var_sku, parent_sku)
                                variacoes.append({
                                    "codigo": var_sku,
                                    "nome": f"Base {var_sku}",
                                    "preco": 0,
                                    "tipo": "P",
                                    "formato": "S",
                                    "situacao": "A",
                                    "variacao": {
                                        "nome": f"Cor:{codes['color']} Tamanho:{codes['size']}",
                                        "ordem": len(variacoes)
                                    }
                                })
                        
                        payload = {
                            "codigo": parent_sku,
                            "nome": existing_data.get("nome", f"Base {parent_sku}"),
                            "tipo": "P",
                            "formato": "V",
                            "situacao": "A",
                            "preco": existing_data.get("preco", 0),
                            "variacoes": variacoes
                        }
                        
                        logger.info(f"Updating {parent_sku} with {len(variacoes)} total variations")
                        result = await client.put(f"/produtos/{existing_id}", payload)
                        logger.info(f"PUT response for {parent_sku}: {result}")
                        results.append({
                            "sku": parent_sku, 
                            "id": existing_id, 
                            "status": "updated",
                            "variations_count": len(variacoes) - len(existing_variations)
                        })
                        logger.info(f"✓ Updated parent {parent_sku}, added {len(variacoes) - len(existing_variations)} new variations")
                    except Exception as e:
                        logger.error(f"✗ Failed to update parent {parent_sku}: {e}", exc_info=True)
                        results.append({"sku": parent_sku, "status": "failed", "error": str(e)})
                else:
                    # Create new parent with variations
                    variacoes = []
                    for var_sku in variations:
                        codes = parse_variation_codes(var_sku, parent_sku)
                        variacoes.append({
                            "codigo": var_sku,
                            "nome": f"Base {var_sku}",
                            "preco": 0,
                            "tipo": "P",
                            "formato": "S",
                            "situacao": "A",
                            "variacao": {
                                "nome": f"Cor:{codes['color']} Tamanho:{codes['size']}",
                                "ordem": len(variacoes)
                            }
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
                    
                    logger.info(f"Creating new parent {parent_sku} with {len(variations)} variations")
                    created_id = await create_product(client, payload)
                    if created_id:
                        results.append({
                            "sku": parent_sku, 
                            "id": created_id, 
                            "status": "created",
                            "variations_count": len(variations)
                        })
                        logger.info(f"✓ Created parent {parent_sku} (id: {created_id}) with {len(variations)} variations")
                    else:
                        results.append({"sku": parent_sku, "status": "failed"})
                        logger.error(f"✗ Failed to create parent {parent_sku}")
        
        await client.client.aclose()
        
        created_results = [r for r in results if r["status"] == "created"]
        updated_results = [r for r in results if r["status"] == "updated"]
        total_variations = sum(r.get("variations_count", 0) for r in created_results + updated_results)
        
        return {
            "results": results,
            "summary": {
                "created_products": len(created_results),
                "updated_products": len(updated_results),
                "created_variations": total_variations,
                "total_items": len(created_results) + len(updated_results) + total_variations
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
