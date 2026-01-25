"""Plan execution API endpoints - Refactored and optimized."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List, Set
from uuid import UUID
from dataclasses import dataclass

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.color_repo import ColorRepository
from app.infra.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/plans", tags=["Plan Execution"])

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SIZE_CODES = ["XG", "GG", "G", "M", "P", "16", "14", "12", "10", "8", "6", "4", "2"]


# ====================================
# Data Classes
# ====================================

@dataclass
class ParsedVariation:
    """Parsed variation data."""
    color: str
    size: str


# ====================================
# Bling Client & Auth
# ====================================

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


# ====================================
# Parsing & Data Extraction
# ====================================

def parse_color_and_size(suffix: str) -> ParsedVariation:
    """Parse color and size from suffix (BRP → BR,P / BRGG → BR,GG)."""
    size = ""
    for size_code in SIZE_CODES:
        if suffix.endswith(size_code):
            size = size_code
            break
    
    color = suffix[:-len(size)] if size else suffix
    return ParsedVariation(color=color, size=size)


def extract_dependencies(item: Dict[str, Any]) -> tuple:
    """Extract parent and base SKUs from hard dependencies."""
    hard = item.get("hard_dependencies") or []
    parent_sku = hard[0] if len(hard) >= 1 else None
    base_sku = hard[1] if len(hard) >= 2 else None
    return parent_sku, base_sku


# ====================================
# Bling API Operations
# ====================================

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


async def create_product(client: BlingClient, payload: Dict[str, Any]) -> Optional[int]:
    """Create product in Bling. Returns product ID."""
    try:
        resp = await client.post("/produtos", payload)
        if isinstance(resp, dict):
            product_id = resp.get("data", {}).get("id")
            return product_id
        return None
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return None


# ====================================
# Payload Building
# ====================================

def _prepare_base_payload(sku: str, name: Optional[str] = None) -> Dict[str, Any]:
    """Build base payload (formato S or V)."""
    return {
        "codigo": sku,
        "nome": name or f"Base {sku}",
        "tipo": "P",
        "situacao": "A",
        "preco": 0,
    }


def _prepare_parent_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Build parent product payload (formato V)."""
    computed = item.get("computed_payload_preview", {})
    payload = _prepare_base_payload(item["sku"], computed.get("nome"))
    
    payload["formato"] = "V"
    payload["descricaoCurta"] = computed.get("descricaoCurta", "")
    payload["descricaoComplementar"] = computed.get("descricaoComplementar", "")
    payload["preco"] = computed.get("preco", 0)
    
    return payload


def _build_variation_item(
    sku: str,
    computed: Dict[str, Any],
    formato: str = "S",
    variacao: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Build a variation/simple product item."""
    item = {
        "codigo": sku,
        "nome": computed.get("nome", sku),
        "preco": computed.get("preco", 0),
        "tipo": "P",
        "formato": formato,
        "situacao": "A",
    }
    
    if variacao:
        item["variacao"] = variacao
    
    return item


def _build_variation_with_composition(
    variation_item: Dict[str, Any],
    base_id: int,
    parent_sku: str,
    color_map: Dict[str, str]
) -> Dict[str, Any]:
    """Build variation with composition (estructura)."""
    sku = variation_item.get("sku", "")
    computed = variation_item.get("computed_payload_preview", {})
    
    # Parse color/size from SKU
    suffix = sku[len(parent_sku):] if sku.startswith(parent_sku) else sku
    parsed = parse_color_and_size(suffix)
    
    color_name = color_map.get(parsed.color, parsed.color)
    variacao_nome = f"Cor: {color_name};Tamanho: {parsed.size}"
    
    item = _build_variation_item(sku, computed, formato="E")
    item["variacao"] = {
        "nome": variacao_nome,
        "ordem": computed.get("variacao", {}).get("ordem", 0),
    }
    item["estrutura"] = {
        "componentes": [{"produto": {"id": base_id}, "quantidade": 1}],
        "tipoEstoque": "V",
        "lancamentoEstoque": "A",
    }
    
    return item


# ====================================
# Variation Merging
# ====================================

def _merge_variations(
    existing_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge existing variations with new ones, updating structure where applicable."""
    new_map = {v.get("codigo"): v for v in new_variations if v.get("codigo")}
    merged = []
    
    for existing_var in existing_variations:
        existing_code = existing_var.get("codigo")
        if existing_code in new_map:
            # Update with new structure
            new_var = new_map[existing_code]
            updated = existing_var.copy()
            
            for field in ["estrutura", "formato", "nome", "preco", "variacao"]:
                if field in new_var:
                    updated[field] = new_var[field]
            
            merged.append(updated)
            del new_map[existing_code]
        else:
            merged.append(existing_var)
    
    # Add new variations
    merged.extend(new_map.values())
    return merged


# ====================================
# Color & Configuration Building
# ====================================

def _build_color_map(plan: Dict[str, Any], db: Session) -> Dict[str, str]:
    """Build color code → name mapping."""
    color_map = {}
    colors = plan.get("colors", []) or []
    
    if not colors:
        db_colors = ColorRepository.list_active(db, TENANT_ID)
        colors = [{"code": c.code, "name": c.name} for c in db_colors]
    
    for c in colors:
        if isinstance(c, dict):
            code = c.get("code", "").upper()
            name = c.get("name", code)
            if code:
                color_map[code] = name
    
    return color_map


# ====================================
# Execution Steps Helpers
# ====================================

def _collect_all_skus(items: List[Dict[str, Any]]) -> Set[str]:
    """Collect all SKUs for bulk checking."""
    skus = set()
    for item in items:
        if sku := item.get("sku"):
            skus.add(sku)
        if item.get("entity") == "VARIATION_PRINTED":
            parent_sku, base_sku = extract_dependencies(item)
            if base_sku:
                skus.add(base_sku)
            if parent_sku:
                skus.add(parent_sku)
    return skus


def _build_children_map(
    items: List[Dict[str, Any]],
    sku_cache: Dict[str, Optional[Dict[str, Any]]],
    color_map: Dict[str, str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Build map of parent SKU → variations with composition."""
    children_map: Dict[str, List[Dict[str, Any]]] = {}
    
    for item in items:
        if item.get("entity") != "VARIATION_PRINTED":
            continue
        
        parent_sku, base_sku = extract_dependencies(item)
        if not parent_sku or not base_sku:
            continue
        
        product = sku_cache.get(base_sku)
        base_id = product.get("id") if product else None
        
        if not base_id:
            logger.warning(f"Base {base_sku} not found for variation {item.get('sku')}")
            continue
        
        variation = _build_variation_with_composition(item, base_id, parent_sku, color_map)
        children_map.setdefault(parent_sku, []).append(variation)
    
    return children_map


# ====================================
# Main Execution Endpoint
# ====================================

@router.post("/execute")
async def execute_plan_direct(plan: Dict[str, Any], db: Session = Depends(get_db)):
    """Execute a plan: create bases → create products → update products.
    
    Flow:
    1. Bulk check all SKUs
    2. Create bases (format V with variations)
    3. Create printed products (format V with format E variations + composition)
    4. Update printed products (add composition to existing variations)
    """
    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling token not configured")

    items = plan.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Plan has no items")
    
    # ========== Bulk load cache ==========
    all_skus = _collect_all_skus(items)
    from app.api.plans import _check_bling_products_bulk
    sku_cache = await _check_bling_products_bulk(client, list(all_skus))
    logger.info(f"Bulk checked {len(all_skus)} SKUs: {sum(1 for v in sku_cache.values() if v)} found")
    
    def get_id_from_cache(sku: str) -> Optional[int]:
        """Get product ID from cache."""
        product = sku_cache.get(sku)
        return product.get("id") if product else None
    
    # ========== Build configuration ==========
    color_map = _build_color_map(plan, db)
    children_map = _build_children_map(items, sku_cache, color_map)
    
    # ========== Track IDs ==========
    base_ids: Dict[str, int] = {}
    parent_ids: Dict[str, int] = {}
    results = []
    
    # ========== STEP 1: CREATE BASE products ==========
    for item in items:
        if item.get("entity") != "BASE_PARENT" or item.get("action") != "CREATE":
            continue

        sku = item["sku"]
        payload = _prepare_base_payload(sku)
        payload["formato"] = "V"
        
        # Collect base variations
        base_variations = []
        for var_item in items:
            if var_item.get("entity") == "BASE_VARIATION" and var_item.get("action") == "CREATE":
                var_sku = var_item.get("sku", "")
                if var_sku.startswith(sku):
                    computed = var_item.get("computed_payload_preview", {})
                    var = _build_variation_item(var_sku, computed, formato="S", variacao=computed.get("variacao", {}))
                    base_variations.append(var)
        
        payload["variacoes"] = base_variations
        logger.info(f"Creating base {sku} with {len(base_variations)} variations")
        
        created_id = await create_product(client, payload)
        if created_id:
            base_ids[sku] = created_id
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "CREATE",
                "id": created_id,
                "status": "success"
            })
        else:
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "CREATE",
                "status": "failed"
            })

    # ========== STEP 2: CREATE PRODUTO (printed parent with variations) ==========
    for item in items:
        if item.get("entity") != "PARENT_PRINTED" or item.get("action") != "CREATE":
            continue

        sku = item["sku"]
        payload = _prepare_parent_payload(item)
        payload["variacoes"] = children_map.get(sku, [])
        
        logger.info(f"Creating produto {sku} with {len(payload['variacoes'])} variations")
        
        created_id = await create_product(client, payload)
        if created_id:
            parent_ids[sku] = created_id
            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "CREATE",
                "id": created_id,
                "status": "success",
                "variations_count": len(payload['variacoes'])
            })
        else:
            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "CREATE",
                "status": "failed"
            })

    # ========== STEP 3: UPDATE PRODUTO (add composition to existing variations) ==========
    for item in items:
        if item.get("entity") != "PARENT_PRINTED" or item.get("action") != "UPDATE":
            continue

        sku = item["sku"]
        existing_id = get_id_from_cache(sku)
        
        if not existing_id:
            logger.warning(f"Cannot update {sku} - not found")
            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "status": "failed",
                "error": "Not found"
            })
            continue
        
        try:
            # Fetch existing product
            existing_product = await client.get(f"/produtos/{existing_id}")
            existing_variations = existing_product.get("data", {}).get("variacoes", [])
            new_variations = children_map.get(sku, [])
            
            # Merge variations
            merged_variations = _merge_variations(existing_variations, new_variations)
            
            payload = _prepare_parent_payload(item)
            payload["variacoes"] = merged_variations
            
            logger.info(f"Updating {sku}: {len(merged_variations)} variations")
            resp = await client.put(f"/produtos/{existing_id}", payload)
            
            if resp:
                parent_ids[sku] = existing_id
                results.append({
                    "sku": sku,
                    "entity": "PARENT_PRINTED",
                    "action": "UPDATE",
                    "id": existing_id,
                    "status": "success",
                    "variations_count": len(merged_variations)
                })
            else:
                results.append({
                    "sku": sku,
                    "entity": "PARENT_PRINTED",
                    "action": "UPDATE",
                    "status": "failed"
                })
        except Exception as e:
            logger.error(f"Error updating {sku}: {e}")
            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "status": "failed",
                "error": str(e)
            })

    # No STEP 4 needed - all variations handled in STEP 2/3

    await client.client.aclose()
    
    # Summary
    success = [r for r in results if r.get("status") == "success"]
    return {
        "status": "completed",
        "total_items": len(items),
        "results": results,
        "summary": {
            "total": len(results),
            "success": len(success),
            "failed": len([r for r in results if r.get("status") == "failed"]),
        }
    }


@router.post("/{plan_id}/execute")
async def execute_plan(plan_id: str, db: Session = Depends(get_db)):
    """Execute a plan by ID (not yet implemented)."""
    raise HTTPException(
        status_code=501,
        detail="Use POST /plans/execute with plan JSON in body"
    )


# ====================================
# Seed Bases Endpoint (Missing Bases Creation)
# ====================================

def _parse_parent_to_variations(
    base_variation_skus: List[str],
    base_parent_skus: List[str],
    model_codes: List[str],
    color_codes: List[str]
) -> Dict[str, List[str]]:
    """Group variations by parent SKU."""
    parent_to_variations: Dict[str, List[str]] = {}
    all_potential_parents = list(set(model_codes + base_parent_skus))
    
    for var_sku in base_variation_skus:
        parent_sku = None
        
        # Try direct match with potential parents
        for potential_parent in all_potential_parents:
            if var_sku.startswith(potential_parent):
                parent_sku = potential_parent
                break
        
        # Parse using size + color if not found
        if not parent_sku:
            for size_code in SIZE_CODES:
                if var_sku.endswith(size_code):
                    prefix_without_size = var_sku[:-len(size_code)]
                    for color_code in color_codes:
                        if prefix_without_size.endswith(color_code):
                            parent_sku = prefix_without_size[:-len(color_code)]
                            break
                    if parent_sku:
                        break
        
        # Fallback: assume color length 2
        if not parent_sku:
            for size_code in SIZE_CODES:
                if var_sku.endswith(size_code) and len(var_sku) > len(size_code) + 2:
                    parent_sku = var_sku[:-len(size_code)-2]
                    break
        
        if parent_sku:
            parent_to_variations.setdefault(parent_sku, []).append(var_sku)
    
    # Ensure all base_parent_skus are in map
    for parent_sku in base_parent_skus:
        parent_to_variations.setdefault(parent_sku, [])
    
    return parent_to_variations


@router.post("/seed-bases")
async def seed_missing_bases(plan: Dict[str, Any], db: Session = Depends(get_db)):
    """Create missing base products (format S or V with variations).
    
    Process:
    1. Parse plan to identify missing bases and variations
    2. Group variations by parent
    3. Create or update base products
    """
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
        
        logger.info(f"Seeding bases: {len(base_parent_skus)} parents, {len(base_variation_skus)} variations")
        
        # Build configuration
        raw_models = plan.get("models", []) or []
        model_codes = [m.get("code", "").upper() for m in raw_models if isinstance(m, dict) and m.get("code")]
        
        color_map = _build_color_map(plan, db)
        color_codes = [c.upper() for c in color_map.keys()]
        
        # Parse parent-to-variations mapping
        parent_to_variations = _parse_parent_to_variations(
            base_variation_skus,
            base_parent_skus,
            model_codes,
            color_codes
        )
        
        if not parent_to_variations:
            logger.warning("No parents parsed for seeding")
            return {
                "results": [],
                "summary": {
                    "created_products": 0,
                    "updated_products": 0,
                    "created_variations": 0,
                    "total_items": 0
                }
            }
        
        # Process each parent
        for parent_sku, variations in parent_to_variations.items():
            existing_id = await fetch_id_by_sku(client, parent_sku)
            
            if not variations:
                # Simple product (no variations)
                if existing_id:
                    logger.info(f"Parent {parent_sku} exists (id: {existing_id}), skipping")
                    results.append({
                        "sku": parent_sku,
                        "id": existing_id,
                        "status": "skipped",
                        "message": "Already exists"
                    })
                    continue
                
                payload = _prepare_base_payload(parent_sku)
                payload["formato"] = "S"
                
                created_id = await create_product(client, payload)
                if created_id:
                    results.append({
                        "sku": parent_sku,
                        "id": created_id,
                        "status": "created",
                        "variations_count": 0
                    })
                    logger.info(f"✓ Created base {parent_sku} (id: {created_id})")
                else:
                    results.append({"sku": parent_sku, "status": "failed"})
                    logger.error(f"✗ Failed to create base {parent_sku}")
            else:
                # Parent with variations
                variacoes = []
                for var_sku in variations:
                    parsed = parse_color_and_size(var_sku[len(parent_sku):])
                    color_name = color_map.get(parsed.color, parsed.color)
                    
                    var = _build_variation_item(
                        var_sku,
                        {"nome": f"Base {var_sku}", "preco": 0},
                        formato="S",
                        variacao={
                            "nome": f"Cor: {color_name};Tamanho: {parsed.size}",
                            "ordem": len(variacoes)
                        }
                    )
                    variacoes.append(var)
                
                payload = _prepare_base_payload(parent_sku)
                payload["formato"] = "V"
                
                if existing_id:
                    # Update existing
                    try:
                        existing_product = await client.get(f"/produtos/{existing_id}")
                        existing_variations = existing_product.get("data", {}).get("variacoes", [])
                        existing_var_skus = {v.get("codigo") for v in existing_variations}
                        
                        # Merge variations
                        new_variacoes = list(existing_variations)
                        for var_sku in variations:
                            if var_sku not in existing_var_skus:
                                new_variacoes.append(
                                    [v for v in variacoes if v.get("codigo") == var_sku][0]
                                )
                        
                        payload["nome"] = existing_product.get("data", {}).get("nome", f"Base {parent_sku}")
                        payload["preco"] = existing_product.get("data", {}).get("preco", 0)
                        payload["variacoes"] = new_variacoes
                        
                        logger.info(f"Updating {parent_sku} with {len(new_variacoes)} total variations")
                        await client.put(f"/produtos/{existing_id}", payload)
                        
                        results.append({
                            "sku": parent_sku,
                            "id": existing_id,
                            "status": "updated",
                            "variations_count": len(new_variacoes) - len(existing_variations)
                        })
                        logger.info(f"✓ Updated {parent_sku}")
                    except Exception as e:
                        logger.error(f"✗ Failed to update {parent_sku}: {e}")
                        results.append({
                            "sku": parent_sku,
                            "status": "failed",
                            "error": str(e)
                        })
                else:
                    # Create new
                    payload["variacoes"] = variacoes
                    
                    logger.info(f"Creating {parent_sku} with {len(variations)} variations")
                    created_id = await create_product(client, payload)
                    
                    if created_id:
                        results.append({
                            "sku": parent_sku,
                            "id": created_id,
                            "status": "created",
                            "variations_count": len(variations)
                        })
                        logger.info(f"✓ Created {parent_sku} (id: {created_id})")
                    else:
                        results.append({"sku": parent_sku, "status": "failed"})
                        logger.error(f"✗ Failed to create {parent_sku}")
        
        await client.client.aclose()
        
        # Summary
        created = [r for r in results if r["status"] == "created"]
        updated = [r for r in results if r["status"] == "updated"]
        total_variations = sum(r.get("variations_count", 0) for r in created + updated)
        
        return {
            "results": results,
            "summary": {
                "created_products": len(created),
                "updated_products": len(updated),
                "created_variations": total_variations,
                "total_items": len(created) + len(updated) + total_variations
            }
        }
    
    except BlingRefreshTokenExpiredError:
        logger.error("Bling token expired")
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception as e:
        logger.error(f"Error seeding bases: {e}")
        raise HTTPException(status_code=500, detail=str(e))
