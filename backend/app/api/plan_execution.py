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


async def create_product_with_error(client: BlingClient, payload: Dict[str, Any]) -> tuple[Optional[int], Optional[str]]:
    """Create product in Bling returning (id, error_message)."""
    try:
        resp = await client.post("/produtos", payload)
        if isinstance(resp, dict):
            product_id = resp.get("data", {}).get("id")
            return product_id, None
        return None, "Bling não retornou ID do produto criado"
    except Exception as e:
        error_msg = _get_error_message(e)
        logger.error(f"Error creating product: {error_msg}")
        return None, error_msg


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


def _apply_fiscal_fields(payload: Dict[str, Any], computed: Dict[str, Any]) -> None:
    """Apply optional fiscal fields from computed payload."""
    if computed.get("ncm"):
        payload["ncm"] = computed.get("ncm")
    if computed.get("cest"):
        payload["cest"] = computed.get("cest")


_WRITABLE_PRODUCT_FIELDS = {
    "nome", "codigo", "tipo", "formato", "situacao", "preco", "precoCusto",
    "descricaoCurta", "descricaoComplementar", "ncm", "cest",
    "peso", "largura", "altura", "comprimento",
    "categoria", "marca", "tributacao", "estoqueMinimo", "estoqueMaximo",
    "unidadeMedida", "linkExterno", "observacoes",
}


def _prepare_parent_payload(item: Dict[str, Any], existing_product: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build parent product payload (formato V).

    Uses a strict whitelist of writable fields taken from existing_product
    so that read-only Bling fields (saldo, imagens, depositos, etc.) are
    never sent in PUT requests, which causes 400 errors.
    """
    computed = item.get("computed_payload_preview") or {}

    # Start from a clean dict with only writable fields preserved from existing product
    if existing_product:
        payload = {
            k: v for k, v in existing_product.items()
            if k in _WRITABLE_PRODUCT_FIELDS
        }
    else:
        payload = {}

    # Always-set fields
    payload["codigo"] = item["sku"]
    payload["tipo"] = "P"
    payload["formato"] = "V"
    payload["situacao"] = "A"

    # Apply computed-preview values (these are the desired new values)
    if "nome" in computed:
        payload["nome"] = computed["nome"]
    if "descricaoCurta" in computed:
        payload["descricaoCurta"] = computed.get("descricaoCurta", "")
    if "descricaoComplementar" in computed:
        payload["descricaoComplementar"] = computed.get("descricaoComplementar", "")
    if "preco" in computed:
        payload["preco"] = computed.get("preco", 0)
    if "ncm" in computed:
        payload["ncm"] = computed.get("ncm")
    if "cest" in computed:
        payload["cest"] = computed.get("cest")

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

    _apply_fiscal_fields(item, computed)
    
    return item


def _build_variation_with_composition(
    variation_item: Dict[str, Any],
    base_id: int,
    parent_sku: str,
    color_map: Dict[str, str]
) -> Dict[str, Any]:
    """Build variation with composition (estructura)."""
    sku = variation_item.get("sku", "")
    computed = variation_item.get("computed_payload_preview") or {}
    
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


def _variation_code(variation: Dict[str, Any]) -> str:
    """Read variation code from common Bling response/payload shapes."""
    if not isinstance(variation, dict):
        return ""

    code = variation.get("codigo")
    if isinstance(code, str) and code.strip():
        return code.strip()

    produto = variation.get("produto")
    if isinstance(produto, dict):
        nested_code = produto.get("codigo")
        if isinstance(nested_code, str) and nested_code.strip():
            return nested_code.strip()

    return ""


def _variation_codes_set(variations: List[Dict[str, Any]]) -> Set[str]:
    """Collect non-empty variation codes from payload/response variations."""
    return {code for code in (_variation_code(v) for v in variations) if code}


def _variation_id(variation: Dict[str, Any]) -> Optional[int]:
    """Read variation product id from common Bling response shapes."""
    if not isinstance(variation, dict):
        return None

    raw_id = variation.get("id")
    if raw_id is None:
        produto = variation.get("produto")
        if isinstance(produto, dict):
            raw_id = produto.get("id")

    if raw_id is None:
        return None

    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _variation_ids_by_code(variations: List[Dict[str, Any]]) -> Dict[str, int]:
    """Build code -> variation product id map for explicit delete operations."""
    result: Dict[str, int] = {}
    for variation in variations:
        code = _variation_code(variation)
        var_id = _variation_id(variation)
        if code and var_id:
            result[code] = var_id
    return result


def _dedupe_variations_by_code(variations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate variations by code while preserving richer payload data."""
    result: List[Dict[str, Any]] = []
    index_by_code: Dict[str, int] = {}

    for variation in variations:
        code = _variation_code(variation)
        if not code:
            result.append(variation)
            continue

        if code not in index_by_code:
            index_by_code[code] = len(result)
            result.append(variation)
            continue

        keep_idx = index_by_code[code]
        kept = result[keep_idx]

        kept_estrutura = kept.get("estrutura") if isinstance(kept, dict) else None
        kept_componentes = kept_estrutura.get("componentes") if isinstance(kept_estrutura, dict) else []
        new_estrutura = variation.get("estrutura") if isinstance(variation, dict) else None
        new_componentes = new_estrutura.get("componentes") if isinstance(new_estrutura, dict) else []

        # New variation payload is the source of truth for mutable business fields.
        # This allows switching stock mode (physical <-> virtual) on updates.
        for field in ["variacao", "formato", "nome", "preco", "ncm", "cest", "utilizarDadosDoPai"]:
            if field in variation:
                kept[field] = variation[field]

        # Keep/replace composition structure according to desired target variation.
        if new_componentes:
            kept["estrutura"] = new_estrutura
        elif variation.get("formato") == "S":
            # Simple variation must not carry composition structure.
            kept.pop("estrutura", None)
        elif (not kept_componentes) and isinstance(new_estrutura, dict):
            kept["estrutura"] = new_estrutura

        result[keep_idx] = kept

    return result


# ====================================
# Variation Merging
# ====================================

def _merge_variations(
    existing_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]],
    sync_selected_only: bool = False,
) -> List[Dict[str, Any]]:
    """Merge existing variations with new ones, updating structure where applicable.
    
    Preserves all existing variation data (especially images) while updating
    only specific fields like estrutura, nome, preco, and variacao.
    
    Strategy: For each existing variation, copy it completely then only update
    the fields provided in new_variations (never delete fields).
    """
    new_map = {_variation_code(v): v for v in new_variations if _variation_code(v)}
    merged = []
    
    for existing_var in existing_variations:
        existing_code = _variation_code(existing_var)
        if existing_code in new_map:
            # Update existing variation with new data
            new_var = new_map[existing_code]
            # Start with complete copy of existing variation (preserves all metadata)
            updated = existing_var.copy()
            
            # Only update these specific fields if provided in new_var
            if "estrutura" in new_var:
                updated["estrutura"] = new_var["estrutura"]
            if "formato" in new_var:
                updated["formato"] = new_var["formato"]
            if "nome" in new_var:
                updated["nome"] = new_var["nome"]
            if "preco" in new_var:
                updated["preco"] = new_var["preco"]
            if "variacao" in new_var:
                updated["variacao"] = new_var["variacao"]
            if "ncm" in new_var:
                updated["ncm"] = new_var["ncm"]
            if "cest" in new_var:
                updated["cest"] = new_var["cest"]
            
            # Explicitly ensure image fields are preserved
            image_fields = ["imagens", "imageUrl", "foto", "fotos", "imagemUrl", "imagemUrls",
                           "imagemPrincipal", "links", "urlImagem", "urlFoto"]
            for image_field in image_fields:
                if image_field in existing_var and image_field not in new_var:
                    # Keep existing image field if not overridden in new_var
                    updated[image_field] = existing_var[image_field]
            
            merged.append(updated)
            del new_map[existing_code]
        else:
            # In sync mode, drop unselected existing variations.
            if not sync_selected_only:
                merged.append(existing_var)
    
    # Add new variations
    merged.extend(new_map.values())
    return _dedupe_variations_by_code(merged)


def _merge_variations_by_name(
    existing_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]],
    sync_selected_only: bool = False,
) -> List[Dict[str, Any]]:
    """Merge variations matching by variacao.nome (Cor: X;Tamanho: Y).

    Used when SKU changes (edit-by-ID mode): preserves existing variation IDs
    and metadata while updating the SKU (codigo) and other fields.
    Variations with no name match are kept as-is; truly new variations are appended.
    """
    new_name_map = {
        v.get("variacao", {}).get("nome", ""): v
        for v in new_variations
        if v.get("variacao", {}).get("nome")
    }
    merged = []
    for existing_var in existing_variations:
        var_name = existing_var.get("variacao", {}).get("nome", "")
        existing_code = _variation_code(existing_var)
        if var_name and var_name in new_name_map:
            new_var = new_name_map.pop(var_name)
            updated = existing_var.copy()  # preserves id, images, etc.
            updated["codigo"] = new_var["codigo"]  # update SKU to new value
            if "estrutura" in new_var:
                updated["estrutura"] = new_var["estrutura"]
            if "formato" in new_var:
                updated["formato"] = new_var["formato"]
            if "nome" in new_var:
                updated["nome"] = new_var["nome"]
            if "preco" in new_var:
                updated["preco"] = new_var["preco"]
            if "variacao" in new_var:
                updated["variacao"] = new_var["variacao"]
            if "ncm" in new_var:
                updated["ncm"] = new_var["ncm"]
            if "cest" in new_var:
                updated["cest"] = new_var["cest"]
            merged.append(updated)
        else:
            # Fallback match by code for cases where variacao.nome is missing.
            matched_by_code = next(
                (nv for nv in new_variations if _variation_code(nv) == existing_code and existing_code),
                None,
            )
            if matched_by_code:
                updated = existing_var.copy()
                for field in ["codigo", "estrutura", "formato", "nome", "preco", "variacao", "ncm", "cest"]:
                    if field in matched_by_code:
                        updated[field] = matched_by_code[field]
                merged.append(updated)
            elif not sync_selected_only:
                merged.append(existing_var)
    # Append truly new variations (no name match found)
    merged.extend(new_name_map.values())
    return _dedupe_variations_by_code(merged)


def _fill_missing_variation_structure(
    merged_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Ensure composition variations carry estrutura when available in new payload.

    Bling validates that variations using composition format include at least one
    component in `estrutura.componentes`. During update flows, some existing
    variations may be kept as-is and therefore miss this structure. This helper
    backfills `estrutura` by matching `variacao.nome` against new variations.
    """
    structure_by_name: Dict[str, Dict[str, Any]] = {}
    for new_var in new_variations:
        var_name = (new_var.get("variacao") or {}).get("nome", "")
        estrutura = new_var.get("estrutura")
        if var_name and isinstance(estrutura, dict):
            componentes = estrutura.get("componentes") or []
            if componentes:
                structure_by_name[var_name] = estrutura

    if not structure_by_name:
        return merged_variations

    for variation in merged_variations:
        var_name = (variation.get("variacao") or {}).get("nome", "")
        if not var_name:
            continue

        target_estrutura = structure_by_name.get(var_name)
        if not target_estrutura:
            continue

        current_estrutura = variation.get("estrutura")
        current_componentes = []
        if isinstance(current_estrutura, dict):
            current_componentes = current_estrutura.get("componentes") or []

        if not current_componentes:
            variation["estrutura"] = target_estrutura

    # Drop any remaining variation that declares composition format but has no
    # valid components — these are "orphan" variations from past failed runs.
    # Keeping them in the PUT payload causes Bling to reject the whole request.
    clean: List[Dict[str, Any]] = []
    new_codes = {_variation_code(v) for v in new_variations}
    for variation in merged_variations:
        estrutura = variation.get("estrutura")
        componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else None
        # A variation is "broken" when it has an empty estrutura AND it's not
        # one we just built (new_codes) — i.e., we have no way to fix it.
        if isinstance(estrutura, dict) and not componentes and _variation_code(variation) not in new_codes:
            logger.warning(
                f"[MERGE] Dropping orphan composition variation "
                f"'{_variation_code(variation)}' — empty estrutura.componentes"
            )
            continue
        clean.append(variation)
    return clean


def _sanitize_variations_for_retry(
    merged_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]],
    is_physical: bool,
) -> List[Dict[str, Any]]:
    """Build a safer variations payload for one retry attempt.

    Strategy:
    - Prefer desired data from `new_variations` when matching by code/name.
    - For physical stock, force simple variations (S) and remove composition.
    - For virtual stock, drop only variations still invalid for composition.
    """
    desired_by_code = {
        _variation_code(v): v
        for v in new_variations
        if _variation_code(v)
    }
    desired_by_name = {
        (v.get("variacao") or {}).get("nome", ""): v
        for v in new_variations
        if (v.get("variacao") or {}).get("nome")
    }

    sanitized: List[Dict[str, Any]] = []
    for current in merged_variations:
        candidate = current.copy()
        code = _variation_code(candidate)
        name = (candidate.get("variacao") or {}).get("nome", "")
        desired = desired_by_code.get(code) or desired_by_name.get(name)

        if desired:
            for field in ["codigo", "nome", "preco", "variacao", "ncm", "cest", "formato", "utilizarDadosDoPai"]:
                if field in desired:
                    candidate[field] = desired[field]
            desired_estrutura = desired.get("estrutura")
            desired_componentes = desired_estrutura.get("componentes") if isinstance(desired_estrutura, dict) else []
            if desired_componentes:
                candidate["estrutura"] = desired_estrutura
            else:
                candidate.pop("estrutura", None)

        if is_physical:
            candidate["formato"] = "S"
            candidate["utilizarDadosDoPai"] = True
            candidate.pop("estrutura", None)
        else:
            formato = (candidate.get("formato") or "").upper()
            estrutura = candidate.get("estrutura")
            componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else []
            if formato == "E" and not componentes:
                # Still invalid for virtual composition; skip in retry payload.
                continue

        sanitized.append(candidate)

    # Ensure all desired variations exist in retry payload.
    existing_codes = {_variation_code(v) for v in sanitized}
    for code, desired in desired_by_code.items():
        if code and code not in existing_codes:
            sanitized.append(desired.copy())

    return _dedupe_variations_by_code(sanitized)


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


def _build_variation_physical(
    sku: str,
    computed: Dict[str, Any],
    parent_sku: str,
    color_map: Dict[str, str]
) -> Dict[str, Any]:
    """Build a physical stock variation (formato S, utilizarDadosDoPai=true)."""
    suffix = sku[len(parent_sku):] if sku.startswith(parent_sku) else sku
    parsed = parse_color_and_size(suffix)
    color_name = color_map.get(parsed.color, parsed.color)
    variacao_nome = f"Cor: {color_name};Tamanho: {parsed.size}"

    item = _build_variation_item(sku, computed, formato="S")
    item["variacao"] = {
        "nome": variacao_nome,
        "ordem": computed.get("variacao", {}).get("ordem", 0),
    }
    item["utilizarDadosDoPai"] = True
    return item


def _build_children_map_physical(
    items: List[Dict[str, Any]],
    color_map: Dict[str, str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Build parent SKU → physical variations map (no composition)."""
    children_map: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        if item.get("entity") != "VARIATION_PRINTED":
            continue
        hard = item.get("hard_dependencies") or []
        parent_sku = hard[0] if hard else None
        if not parent_sku:
            continue
        sku = item["sku"]
        computed = item.get("computed_payload_preview") or {}
        variation = _build_variation_physical(sku, computed, parent_sku, color_map)
        children_map.setdefault(parent_sku, []).append(variation)
    return children_map


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


def _get_error_message(error: Exception) -> str:
    """Extract human-readable error message."""
    return str(error) if error else "Erro desconhecido"


async def _mark_product_as_excluded(client: BlingClient, product_id: int) -> Optional[str]:
    """Try to set product status to excluded in Bling.

    Some Bling accounts require product `situacao` to be excluded before
    definitive DELETE is accepted (validation code 12).
    Returns None on success, or an error message on failure.
    """
    # First try minimal payload (often accepted for status-only updates).
    try:
        await client.put(f"/produtos/{product_id}", {"situacao": "E"})
        return None
    except Exception:
        pass

    # Fallback: send a writable snapshot from current product detail.
    try:
        existing_product = await client.get(f"/produtos/{product_id}")
        existing_data = (existing_product or {}).get("data", {})
        payload = {
            k: v for k, v in existing_data.items()
            if k in _WRITABLE_PRODUCT_FIELDS
        }
        payload["situacao"] = "E"
        if "tipo" not in payload:
            payload["tipo"] = "P"
        await client.put(f"/produtos/{product_id}", payload)
        return None
    except Exception as e:
        return _get_error_message(e)


async def _delete_product_with_fallback(client: BlingClient, product_id: int) -> tuple[bool, Optional[str]]:
    """Delete product, retrying after marking status as excluded when needed."""
    try:
        await client.delete(f"/produtos/{product_id}")
        return True, None
    except Exception as first_delete_error:
        first_msg = _get_error_message(first_delete_error)

    exclude_error = await _mark_product_as_excluded(client, product_id)
    if exclude_error:
        return False, (
            f"falha ao excluir: {first_msg}; "
            f"falha ao marcar como excluido: {exclude_error}"
        )

    try:
        await client.delete(f"/produtos/{product_id}")
        return True, None
    except Exception as second_delete_error:
        second_msg = _get_error_message(second_delete_error)
        return False, (
            f"falha ao excluir: {first_msg}; "
            f"apos marcar como excluido: {second_msg}"
        )


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

    stock_type = (plan.get("options") or {}).get("stock_type", "virtual")
    is_physical = stock_type == "physical"
    
    # ========== Bulk load cache ==========
    all_skus = _collect_all_skus(items)
    from app.api.plans import _check_bling_products_bulk
    sku_cache = await _check_bling_products_bulk(client, list(all_skus))
    logger.debug(f"Bulk checked {len(all_skus)} SKUs")
    
    def get_id_from_cache(sku: str) -> Optional[int]:
        """Get product ID from cache."""
        product = sku_cache.get(sku)
        return product.get("id") if product else None
    
    # ========== Build configuration ==========
    color_map = _build_color_map(plan, db)
    if is_physical:
        children_map = _build_children_map_physical(items, color_map)
    else:
        children_map = _build_children_map(items, sku_cache, color_map)
    
    # ========== Track IDs ==========
    base_ids: Dict[str, int] = {}
    parent_ids: Dict[str, int] = {}
    results = []
    processed_target_ids: Set[int] = set()
    
    # ========== STEP 1: CREATE BASE products ==========
    for item in items:
        if item.get("entity") != "BASE_PARENT" or item.get("action") != "CREATE":
            continue

        sku = item["sku"]
        computed = item.get("computed_payload_preview") or {}
        payload = _prepare_base_payload(sku, computed.get("nome"))
        payload["formato"] = "V"
        if "preco" in computed:
            payload["preco"] = computed.get("preco", 0)
        _apply_fiscal_fields(payload, computed)
        
        # Collect base variations
        base_variations = []
        for var_item in items:
            if var_item.get("entity") == "BASE_VARIATION" and var_item.get("action") == "CREATE":
                var_sku = var_item.get("sku", "")
                if var_sku.startswith(sku):
                    computed = var_item.get("computed_payload_preview") or {}
                    var = _build_variation_item(var_sku, computed, formato="S", variacao=computed.get("variacao", {}))
                    base_variations.append(var)
        
        payload["variacoes"] = base_variations
        logger.debug(f"Creating base {sku}")
        
        created_id, create_error = await create_product_with_error(client, payload)
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
                "status": "failed",
                "error": create_error or "Falha ao criar base no Bling",
            })

    # ========== STEP 2: CREATE PRODUTO (printed parent with variations) ==========
    for item in items:
        if item.get("entity") != "PARENT_PRINTED" or item.get("action") != "CREATE":
            continue

        sku = item["sku"]
        payload = _prepare_parent_payload(item)
        payload["variacoes"] = children_map.get(sku, [])
        
        logger.debug(f"Creating produto {sku}")
        
        created_id, create_error = await create_product_with_error(client, payload)
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
            recovered = False
            recovery_error_msg = None
            error_message = create_error or "Falha ao criar produto no Bling"
            is_duplicate_code = (
                "código" in (error_message or "").lower()
                and "já foi cadastrado" in (error_message or "").lower()
            )

            # Auto-recovery: when CREATE fails due duplicate variation SKUs,
            # find the existing parent by those variations and apply UPDATE.
            if is_duplicate_code and payload.get("variacoes"):
                try:
                    inferred_parent_ids: List[int] = []
                    for var in payload.get("variacoes", []):
                        var_code = _variation_code(var)
                        if not var_code:
                            continue

                        var_id = get_id_from_cache(var_code)
                        if not var_id:
                            var_id = await fetch_id_by_sku(client, var_code)
                        if not var_id:
                            continue

                        var_detail = await client.get(f"/produtos/{var_id}")
                        var_data = var_detail.get("data", {})
                        parent_id = (
                            ((var_data.get("variacao") or {}).get("produtoPai") or {}).get("id")
                            or var_data.get("idProdutoPai")
                            or var_data.get("pai")
                        )
                        if parent_id:
                            inferred_parent_ids.append(parent_id)

                    if inferred_parent_ids:
                        candidate_parent_id = max(
                            set(inferred_parent_ids),
                            key=inferred_parent_ids.count,
                        )

                        existing_parent = await client.get(f"/produtos/{candidate_parent_id}")
                        existing_parent_data = existing_parent.get("data", {})
                        existing_variations = existing_parent_data.get("variacoes", [])
                        existing_codes = _variation_codes_set(existing_variations)
                        selected_codes = _variation_codes_set(payload.get("variacoes", []))

                        merged_variations = _merge_variations(
                            existing_variations,
                            payload.get("variacoes", []),
                            sync_selected_only=True,
                        )
                        merged_variations = _fill_missing_variation_structure(
                            merged_variations,
                            payload.get("variacoes", []),
                        )
                        merged_codes = _variation_codes_set(merged_variations)
                        removed_codes = sorted(existing_codes - merged_codes)
                        existing_ids_by_code = _variation_ids_by_code(existing_variations)
                        removed_deleted_count = 0
                        removed_delete_failed: List[str] = []

                        for removed_code in removed_codes:
                            removed_id = existing_ids_by_code.get(removed_code)
                            if not removed_id:
                                removed_delete_failed.append(
                                    f"{removed_code} (sem id para exclusao)"
                                )
                                continue
                            deleted, delete_error = await _delete_product_with_fallback(client, removed_id)
                            if deleted:
                                removed_deleted_count += 1
                            else:
                                removed_delete_failed.append(
                                    f"{removed_code} (id={removed_id}): {delete_error}"
                                )
                        if removed_codes:
                            logger.info(
                                f"[SYNC] {sku}: requested remove={len(removed_codes)}, "
                                f"deleted={removed_deleted_count}, failed={len(removed_delete_failed)}"
                            )

                        retry_payload = _prepare_parent_payload(item, existing_parent_data)
                        retry_payload["variacoes"] = merged_variations

                        await client.put(f"/produtos/{candidate_parent_id}", retry_payload)

                        parent_ids[sku] = candidate_parent_id
                        results.append({
                            "sku": sku,
                            "entity": "PARENT_PRINTED",
                            "action": "UPDATE",
                            "id": candidate_parent_id,
                            "status": "success",
                            "variations_count": len(merged_variations),
                            "selected_variations_count": len(selected_codes),
                            "removed_variations_count": len(removed_codes),
                            "removed_variations": removed_codes,
                            "removed_variations_deleted_count": removed_deleted_count,
                            "removed_variations_delete_failed": removed_delete_failed,
                            "recovery_mode": "create_conflict_updated_existing_parent",
                        })
                        recovered = True
                except Exception as recovery_error:
                    recovery_error_msg = _get_error_message(recovery_error)
                    logger.warning(
                        f"[CREATE RECOVERY] Failed to recover {sku} after duplicate code error: "
                        f"{recovery_error_msg}"
                    )

            if recovered:
                continue

            if is_duplicate_code:
                suggestion = (
                    "Dica: o pai foi planejado como CREATE, mas as variações já existem no Bling. "
                    "Use o produto pai existente (editar por ID) ou remova/renomeie os SKUs de variação conflitantes."
                )
                if recovery_error_msg:
                    suggestion = f"{suggestion} Tentativa automática de recuperação falhou: {recovery_error_msg}"
                error_message = f"{error_message}. {suggestion}"

            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "CREATE",
                "status": "failed",
                "error": error_message,
            })

    # ========== STEP 3: UPDATE PRODUTO (add composition to existing variations) ==========
    for item in items:
        if item.get("entity") != "PARENT_PRINTED" or item.get("action") != "UPDATE":
            continue

        sku = item["sku"]
        force_update_id = item.get("force_update_id")
        orphan_warning = None

        # Resolve the target product id safely:
        # - force_update_id is authoritative in edit-by-id mode (can have different current codigo)
        # - cache-derived id must match sku to avoid cross-updating a different parent
        existing_id = None
        existing_product_data: Dict[str, Any] = {}

        if force_update_id:
            try:
                forced_product = await client.get(f"/produtos/{force_update_id}")
                existing_id = force_update_id
                existing_product_data = forced_product.get("data", {})
                logger.info(
                    f"[UPDATE] Using force_update_id={force_update_id} for {sku} "
                    f"(current codigo={existing_product_data.get('codigo')})"
                )
            except Exception as forced_error:
                logger.warning(
                    f"[UPDATE] Failed to fetch force_update_id {force_update_id} for {sku}: "
                    f"{_get_error_message(forced_error)}"
                )

        if not existing_id:
            cache_id = get_id_from_cache(sku)
            if cache_id:
                try:
                    cached_product = await client.get(f"/produtos/{cache_id}")
                    cached_data = cached_product.get("data", {})
                    cached_code = (cached_data.get("codigo") or "").strip().upper()
                    if cached_code == sku.strip().upper():
                        existing_id = cache_id
                        existing_product_data = cached_data
                    else:
                        logger.warning(
                            f"[UPDATE] Ignoring mismatched target id for {sku}: "
                            f"candidate_id={cache_id} has codigo={cached_data.get('codigo')}"
                        )
                except Exception as cached_error:
                    logger.warning(
                        f"[UPDATE] Failed to validate cache target id {cache_id} for {sku}: "
                        f"{_get_error_message(cached_error)}"
                    )

        if not existing_id:
            looked_up_id = await fetch_id_by_sku(client, sku)
            if looked_up_id:
                looked_up_product = await client.get(f"/produtos/{looked_up_id}")
                existing_id = looked_up_id
                existing_product_data = looked_up_product.get("data", {})

        if not existing_id:
            logger.warning(f"Cannot update {sku} - not found")
            results.append({
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "status": "failed",
                "error": "Not found",
                "target_id": None,
            })
            continue
        
        try:
            existing_variations = existing_product_data.get("variacoes", [])
            new_variations = children_map.get(sku, [])
            existing_codes = _variation_codes_set(existing_variations)
            selected_codes = _variation_codes_set(new_variations)
            
            # Merge variations (by name when editing by ID to handle SKU renames)
            if force_update_id:
                merged_variations = _merge_variations_by_name(
                    existing_variations,
                    new_variations,
                    sync_selected_only=True,
                )
            else:
                merged_variations = _merge_variations(
                    existing_variations,
                    new_variations,
                    sync_selected_only=True,
                )
            merged_variations = _fill_missing_variation_structure(merged_variations, new_variations)
            merged_codes = _variation_codes_set(merged_variations)
            removed_codes = sorted(existing_codes - merged_codes)
            existing_ids_by_code = _variation_ids_by_code(existing_variations)
            removed_deleted_count = 0
            removed_delete_failed: List[str] = []

            for removed_code in removed_codes:
                removed_id = existing_ids_by_code.get(removed_code)
                if not removed_id:
                    removed_delete_failed.append(
                        f"{removed_code} (sem id para exclusao)"
                    )
                    continue
                deleted, delete_error = await _delete_product_with_fallback(client, removed_id)
                if deleted:
                    removed_deleted_count += 1
                else:
                    removed_delete_failed.append(
                        f"{removed_code} (id={removed_id}): {delete_error}"
                    )

            if removed_codes:
                logger.info(
                    f"[SYNC] {sku}: requested remove={len(removed_codes)}, "
                    f"deleted={removed_deleted_count}, failed={len(removed_delete_failed)}"
                )

            # Detect orphan variations that STILL have empty estrutura after all merging.
            # These are ghost variations in Bling from previous failed runs that cannot
            # be fixed automatically — they require manual deletion in Bling.
            orphan_variations = []
            for var in existing_variations:
                code = _variation_code(var)
                estrutura = var.get("estrutura")
                componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else None
                if isinstance(estrutura, dict) and not componentes:
                    # Check if it ended up fixed in merged payload
                    merged_code_has_struct = any(
                        _variation_code(mv) == code
                        and isinstance(mv.get("estrutura"), dict)
                        and mv.get("estrutura", {}).get("componentes")
                        for mv in merged_variations
                    )
                    if not merged_code_has_struct:
                        orphan_variations.append(code or f"índice {existing_variations.index(var)}")

            if orphan_variations:
                logger.warning(
                    f"[ORPHAN] {sku} (id={existing_id}) has {len(orphan_variations)} orphan "
                    f"composition variation(s): {orphan_variations}"
                )
                if is_physical:
                    # Physical stock: orphan composition variations are simply wrong format.
                    # Convert them to simple (S) by removing estrutura — no composition needed.
                    fixed = 0
                    for mv in merged_variations:
                        if _variation_code(mv) in orphan_variations:
                            mv["formato"] = "S"
                            mv.pop("estrutura", None)
                            fixed += 1
                    logger.info(
                        f"[ORPHAN] Physical mode: converted {fixed} orphan variation(s) to "
                        f"formato=S for {sku}"
                    )
                else:
                    # Virtual stock: try to persist using sanitized payload first.
                    # We already dropped invalid orphan variations from merged payload;
                    # if PUT succeeds, no manual action is needed.
                    orphan_warning = {
                        "error_type": "orphan_composition_variations",
                        "orphan_variations": orphan_variations,
                        "bling_product_id": existing_id,
                        "warning": (
                            f"Foram detectadas {len(orphan_variations)} variação(ões) órfãs com "
                            f"composição inválida. Tentando atualizar com payload saneado."
                        ),
                    }

            # Pass existing product to preserve images/links
            payload = _prepare_parent_payload(item, existing_product_data)
            payload["variacoes"] = merged_variations
            try:
                resp = await client.put(f"/produtos/{existing_id}", payload)
            except Exception as first_put_error:
                # One automatic retry with sanitized variations before surfacing error.
                retry_variations = _sanitize_variations_for_retry(
                    merged_variations=merged_variations,
                    new_variations=new_variations,
                    is_physical=is_physical,
                )

                if retry_variations and retry_variations != merged_variations:
                    logger.warning(
                        f"[RETRY] PUT failed for {sku} (id={existing_id}). "
                        f"Retrying with sanitized variations payload: "
                        f"{len(merged_variations)} -> {len(retry_variations)}"
                    )
                    payload["variacoes"] = retry_variations
                    resp = await client.put(f"/produtos/{existing_id}", payload)
                    merged_variations = retry_variations
                else:
                    raise first_put_error
            
            if resp:
                parent_ids[sku] = existing_id
                result_item = {
                    "sku": sku,
                    "entity": "PARENT_PRINTED",
                    "action": "UPDATE",
                    "id": existing_id,
                    "status": "success",
                    "variations_count": len(merged_variations),
                    "selected_variations_count": len(selected_codes),
                    "removed_variations_count": len(removed_codes),
                    "removed_variations": removed_codes,
                    "removed_variations_deleted_count": removed_deleted_count,
                    "removed_variations_delete_failed": removed_delete_failed,
                }
                if orphan_warning:
                    result_item.update(orphan_warning)
                results.append(result_item)
            else:
                result_item = {
                    "sku": sku,
                    "entity": "PARENT_PRINTED",
                    "action": "UPDATE",
                    "status": "failed",
                    "target_id": existing_id,
                    "error": "Falha ao atualizar produto no Bling",
                }
                if orphan_warning:
                    result_item.update(orphan_warning)
                results.append(result_item)
        except Exception as e:
            logger.error(f"Error updating {sku}: {e}")
            result_item = {
                "sku": sku,
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "status": "failed",
                "error": _get_error_message(e),
                "target_id": existing_id,
            }
            # Keep context if orphan cleanup was attempted in this run.
            if 'orphan_warning' in locals() and orphan_warning:
                result_item.update(orphan_warning)
            results.append(result_item)

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


@router.post("/recreate-failed-updates")
async def recreate_failed_updates(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Delete and recreate products that failed in UPDATE step (only when explicitly requested)."""
    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling token not configured")

    plan = payload.get("plan") or {}
    failed_update_skus = set(payload.get("failed_update_skus") or [])

    if not failed_update_skus:
        raise HTTPException(status_code=400, detail="Nenhum SKU de falha informado para recriação")

    items = plan.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Plano inválido: sem itens")

    stock_type = (plan.get("options") or {}).get("stock_type", "virtual")
    is_physical = stock_type == "physical"

    all_skus = _collect_all_skus(items)
    from app.api.plans import _check_bling_products_bulk
    sku_cache = await _check_bling_products_bulk(client, list(all_skus))

    color_map = _build_color_map(plan, db)
    if is_physical:
        children_map = _build_children_map_physical(items, color_map)
    else:
        children_map = _build_children_map(items, sku_cache, color_map)

    def get_id_from_cache(sku: str) -> Optional[int]:
        product = sku_cache.get(sku)
        return product.get("id") if product else None

    candidates = [
        item for item in items
        if item.get("entity") == "PARENT_PRINTED"
        and item.get("action") == "UPDATE"
        and item.get("sku") in failed_update_skus
    ]

    if not candidates:
        await client.client.aclose()
        return {
            "results": [],
            "summary": {
                "requested": len(failed_update_skus),
                "processed": 0,
                "recreated": 0,
                "failed": 0,
            }
        }

    results = []

    try:
        for item in candidates:
            sku = item.get("sku")
            target_id = item.get("force_update_id") or get_id_from_cache(sku)

            if not target_id:
                target_id = await fetch_id_by_sku(client, sku)

            if not target_id:
                results.append({
                    "sku": sku,
                    "status": "failed",
                    "error": "Produto não encontrado para excluir antes da recriação",
                })
                continue

            if target_id in processed_target_ids:
                results.append({
                    "sku": sku,
                    "status": "skipped",
                    "target_id": target_id,
                    "reason": "Mesmo produto já processado nesta recriação",
                })
                continue
            processed_target_ids.add(target_id)

            create_payload = _prepare_parent_payload(item)
            create_payload["variacoes"] = children_map.get(sku, [])

            deleted = False
            delete_error_message = None

            try:
                await client.delete(f"/produtos/{target_id}")
                deleted = True
            except Exception as e:
                delete_error_message = _get_error_message(e)
                logger.warning(
                    f"[RECREATE] Delete blocked for {sku} (id={target_id}): {delete_error_message}. "
                    f"Trying in-place rebuild as fallback."
                )

            if not deleted:
                # Fallback when Bling blocks delete (e.g. product not in excluded state):
                # try to rebuild in-place using PUT on the same product id.
                try:
                    existing_product = await client.get(f"/produtos/{target_id}")
                    existing_product_data = existing_product.get("data", {})

                    in_place_payload = _prepare_parent_payload(item, existing_product_data)
                    # In-place recovery must keep the current code to avoid duplicate-SKU
                    # validation when another product already uses item.sku.
                    in_place_payload["codigo"] = existing_product_data.get("codigo") or item.get("sku")
                    in_place_payload["variacoes"] = create_payload.get("variacoes", [])

                    await client.put(f"/produtos/{target_id}", in_place_payload)
                    results.append({
                        "sku": sku,
                        "status": "recreated",
                        "old_id": target_id,
                        "new_id": target_id,
                        "recovery_mode": "in_place_update",
                        "warning": (
                            "Exclusão bloqueada no Bling; produto foi reconstruído no mesmo ID "
                            "com atualização direta."
                        ),
                        "delete_error": delete_error_message,
                    })
                    continue
                except Exception as in_place_error:
                    results.append({
                        "sku": sku,
                        "status": "failed",
                        "error": (
                            f"Falha ao excluir produto {target_id}: {delete_error_message}. "
                            f"Fallback de reconstrução no mesmo ID também falhou: "
                            f"{_get_error_message(in_place_error)}"
                        ),
                        "old_id": target_id,
                    })
                    continue

            created_id = await create_product(client, create_payload)
            if created_id:
                results.append({
                    "sku": sku,
                    "status": "recreated",
                    "old_id": target_id,
                    "new_id": created_id,
                })
            else:
                results.append({
                    "sku": sku,
                    "status": "failed",
                    "error": "Produto excluído, mas recriação falhou",
                    "old_id": target_id,
                })

        recreated = [r for r in results if r.get("status") == "recreated"]
        failed = [r for r in results if r.get("status") == "failed"]

        return {
            "results": results,
            "summary": {
                "requested": len(failed_update_skus),
                "processed": len(results),
                "recreated": len(recreated),
                "failed": len(failed),
            }
        }
    finally:
        await client.client.aclose()


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
        
        logger.debug(f"Seeding bases")
        
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
                    logger.debug(f"Parent {parent_sku} exists, skipping")
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
                    logger.debug(f"✓ Created base {parent_sku}")
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
                        
                        logger.debug(f"Updating {parent_sku}")
                        await client.put(f"/produtos/{existing_id}", payload)
                        
                        results.append({
                            "sku": parent_sku,
                            "id": existing_id,
                            "status": "updated",
                            "variations_count": len(new_variacoes) - len(existing_variations)
                        })
                        logger.debug(f"✓ Updated {parent_sku}")
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
                    
                    logger.debug(f"Creating {parent_sku}")
                    created_id = await create_product(client, payload)
                    
                    if created_id:
                        results.append({
                            "sku": parent_sku,
                            "id": created_id,
                            "status": "created",
                            "variations_count": len(variations)
                        })
                        logger.debug(f"✓ Created {parent_sku}")
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
