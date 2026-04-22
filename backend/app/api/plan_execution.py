"""Plan execution API endpoints - Refactored and optimized."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List, Set
from uuid import UUID
from dataclasses import dataclass
from celery.result import AsyncResult

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingRefreshTokenExpiredError
from app.repositories.bling_token_repo import BlingTokenRepository
from app.repositories.color_repo import ColorRepository
from app.repositories.product_snapshot_repo import ProductSnapshotRepository
from app.infra.logging import get_logger
from app.models.schemas import PlanPlainRequest, PlanResponse, ErrorResponse
from app.models.enums import ProductKindEnum
from app.settings import settings
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
router = APIRouter(prefix="/plans", tags=["Plan Execution"])

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SIZE_CODES = ["XG", "GG", "G", "M", "P", "16", "14", "12", "10", "8", "6", "4", "2"]


@router.post(
    "/new-plain",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def create_new_plain_plan_fallback(
    request: PlanPlainRequest,
    db: Session = Depends(get_db),
):
    """Fallback proxy for plain plan generation using the plans API implementation."""
    from app.api import plans as plans_api

    return await plans_api.create_new_plain_plan(request, db)


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

def _prepare_base_payload(sku: str, name: Optional[str] = None, computed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build base payload (formato S or V).
    
    Applies template fields from computed payload (marca, condição, tipo, unidade, 
    peso, altura, largura, etc.) to ensure new products inherit template attributes.
    """
    computed = computed or {}
    payload = {
        "codigo": sku,
        "nome": name or f"Base {sku}",
        "tipo": "P",
        "situacao": "A",
        "preco": 0,
    }
    
    _apply_template_fields(payload, computed)
    
    return payload


def _apply_fiscal_fields(payload: Dict[str, Any], computed: Dict[str, Any]) -> None:
    """Apply fiscal fields from computed payload into tributacao (Bling V3 structure).

    In Bling V3 API, NCM and CEST are nested inside ``tributacao``, not top-level.
    This function always writes them to ``payload["tributacao"]``.
    """
    # Ensure tributacao exists in payload
    if not isinstance(payload.get("tributacao"), dict):
        payload["tributacao"] = {}

    computed_trib = computed.get("tributacao") or {}

    # NCM from computed.tributacao (Wizard form value placed there by TemplateMerge)
    ncm_value = computed_trib.get("ncm")
    if ncm_value is not None:
        payload["tributacao"]["ncm"] = str(ncm_value)
    elif "ncm" not in payload["tributacao"]:
        payload["tributacao"]["ncm"] = ""

    # CEST from computed.tributacao
    cest_value = computed_trib.get("cest")
    if cest_value is not None:
        payload["tributacao"]["cest"] = str(cest_value)
    elif "cest" not in payload["tributacao"]:
        payload["tributacao"]["cest"] = ""

    # spedTipoItem - default to "04" if not set
    sped = computed_trib.get("spedTipoItem")
    if sped:
        payload["tributacao"]["spedTipoItem"] = sped
    elif not payload["tributacao"].get("spedTipoItem"):
        payload["tributacao"]["spedTipoItem"] = "04"


_ESTOQUE_SETTINGS_KEYS = ("minimo", "maximo", "crossdocking", "localizacao")


def _apply_template_fields(payload: Dict[str, Any], computed: Dict[str, Any]) -> None:
    """Apply template/computed fields using Bling-compatible keys.

    Handles Bling V3 nested objects:
    - ``dimensoes`` for largura/altura/profundidade
    - ``estoque`` for minimo/maximo/crossdocking
    - ``tributacao`` for ncm/cest/spedTipoItem (handled separately by _apply_fiscal_fields)
    """
    if not isinstance(computed, dict):
        return

    direct_fields = {
        "nome", "descricaoCurta", "descricaoComplementar", "preco", "precoCusto",
        "marca", "condicao", "unidade", "unidadeMedida", "peso", "pesoLiquido", "pesoBruto",
        "tributacao", "linkExterno", "observacoes",
        "categoria", "tipoProducao", "freteGratis", "volumes", "itensPorCaixa", "gtin", "gtinEmbalagem",
    }

    for field in direct_fields:
        if field in computed and computed[field] is not None:
            payload[field] = computed[field]

    # Category override may arrive as categoria_id.
    categoria_id = computed.get("categoria_id")
    if categoria_id is not None and not payload.get("categoria"):
        payload["categoria"] = {"id": categoria_id}

    # Dimensions (largura, altura, profundidade) live inside ``dimensoes`` in Bling V3.
    if isinstance(computed.get("dimensoes"), dict):
        payload["dimensoes"] = computed["dimensoes"]

    # Stock settings (minimo, maximo, crossdocking, localizacao) live inside ``estoque``.
    computed_estoque = computed.get("estoque")
    if isinstance(computed_estoque, dict):
        settings = {k: v for k, v in computed_estoque.items() if k in _ESTOQUE_SETTINGS_KEYS and v is not None}
        if settings:
            if not isinstance(payload.get("estoque"), dict):
                payload["estoque"] = {}
            payload["estoque"].update(settings)


# Bling V3 field names that can be written in PUT/POST requests.
# Note: ncm/cest are inside ``tributacao``, largura/altura/profundidade are inside
# ``dimensoes``. ``estoque`` (minimo/maximo/crossdocking) is NOT copied from existing product
# to avoid sending the computed ``saldo`` field; it is always applied from the template
# via _apply_template_fields.
_WRITABLE_PRODUCT_FIELDS = {
    "nome", "codigo", "tipo", "formato", "situacao", "preco", "precoCusto",
    "descricaoCurta", "descricaoComplementar",
    "peso", "pesoLiquido", "pesoBruto",
    "categoria", "marca", "tributacao",
    "unidade", "unidadeMedida", "dimensoes", "condicao", "linkExterno", "observacoes",
    "tipoProducao", "freteGratis", "volumes", "itensPorCaixa", "gtin", "gtinEmbalagem",
}

_WRITABLE_VARIATION_FIELDS = {
    "id",
    "codigo", "nome", "tipo", "formato", "situacao", "preco", "precoCusto",
    "descricaoCurta", "descricaoComplementar",
    "peso", "pesoLiquido", "pesoBruto",
    "categoria", "marca", "tributacao", "unidade", "unidadeMedida", "dimensoes", "condicao",
    "variacao", "estrutura", "utilizarDadosDoPai", "observacoes",
    "tipoProducao", "freteGratis", "volumes", "itensPorCaixa", "gtin", "gtinEmbalagem",
}


def _prepare_parent_payload(item: Dict[str, Any], existing_product: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build parent product payload (formato V).

    Uses a strict whitelist of writable fields taken from existing_product
    so that read-only Bling fields (saldo, imagens, depositos, etc.) are
    never sent in PUT requests, which causes 400 errors.
    
    Applies all template fields (marca, condição, tipo, unidade, peso, altura, largura, etc.)
    ensuring data integrity from base template.
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

    # Apply template/computed values preserving Bling field names.
    _apply_template_fields(payload, computed)

    # Ensure fiscal fields are properly set
    _apply_fiscal_fields(payload, computed)

    return payload


def _build_variation_item(
    sku: str,
    computed: Dict[str, Any],
    formato: str = "S",
    variacao: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Build a variation/simple product item.
    
    Applies all template fields to ensure variation inherits attributes from base template
    (marca, condição, tipo, unidade, peso, altura, largura, etc.)
    """
    item = {
        "codigo": sku,
        "nome": computed.get("nome", sku),
        "preco": computed.get("preco", 0),
        "tipo": "P",
        "formato": formato,
        "situacao": "A",
    }

    _apply_template_fields(item, computed)

    raw_variacao = variacao if isinstance(variacao, dict) else {}
    fallback_variacao = computed.get("variacao") if isinstance(computed.get("variacao"), dict) else {}
    variacao_nome = str(
        raw_variacao.get("nome")
        or fallback_variacao.get("nome")
        or f"SKU: {sku}"
    ).strip()
    variacao_ordem = raw_variacao.get("ordem")
    if variacao_ordem is None:
        variacao_ordem = fallback_variacao.get("ordem", 0)

    item["variacao"] = {
        "nome": variacao_nome,
        "ordem": variacao_ordem,
    }

    _apply_fiscal_fields(item, computed)

    return item


def _sanitize_variation_for_put(variation: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only writable variation fields before sending PUT/POST to Bling."""
    cleaned = {
        k: v for k, v in (variation or {}).items()
        if k in _WRITABLE_VARIATION_FIELDS
    }

    # Preserve variation id when available so parent PUT updates existing
    # variations instead of attempting duplicate creations by code/name.
    raw_id = cleaned.get("id")
    if raw_id is not None:
        try:
            cleaned["id"] = int(raw_id)
        except (TypeError, ValueError):
            cleaned.pop("id", None)

    sku = str(cleaned.get("codigo") or _variation_code(variation) or "").strip()
    raw_variacao = cleaned.get("variacao")
    raw_nome = ""
    raw_ordem = 0
    if isinstance(raw_variacao, dict):
        raw_nome = str(raw_variacao.get("nome") or "").strip()
        raw_ordem = raw_variacao.get("ordem", 0)
    elif isinstance(raw_variacao, str):
        raw_nome = raw_variacao.strip()

    cleaned["variacao"] = {
        "nome": raw_nome or (f"SKU: {sku}" if sku else "Variação"),
        "ordem": raw_ordem,
    }

    formato = str(cleaned.get("formato") or "S").strip().upper()
    cleaned["formato"] = formato

    if formato == "E":
        estrutura = cleaned.get("estrutura") if isinstance(cleaned.get("estrutura"), dict) else {}
        componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else []
        safe_componentes = []
        for componente in componentes or []:
            if not isinstance(componente, dict):
                continue
            produto = componente.get("produto") if isinstance(componente.get("produto"), dict) else {}
            produto_id = produto.get("id")
            quantidade = componente.get("quantidade", 1)
            if not produto_id:
                continue
            safe_componentes.append({
                "produto": {"id": produto_id},
                "quantidade": quantidade,
            })

        if safe_componentes:
            cleaned["estrutura"] = {
                "componentes": safe_componentes,
                "tipoEstoque": (estrutura.get("tipoEstoque") or "V"),
                "lancamentoEstoque": (estrutura.get("lancamentoEstoque") or "A"),
            }
        else:
            cleaned.pop("estrutura", None)
    else:
        cleaned.pop("estrutura", None)

    return cleaned


def _log_variation_payload_shape(tag: str, sku: str, variations: List[Dict[str, Any]]) -> None:
    """Log only payload shape (keys/counts) to troubleshoot 400 without leaking content."""
    sample_keys = sorted({k for v in (variations or []) for k in (v.keys() if isinstance(v, dict) else [])})
    logger.info(
        f"[{tag}] sku={sku} variacoes={len(variations or [])} keys={sample_keys}"
    )


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


def _orphan_composition_codes(variations: List[Dict[str, Any]]) -> Set[str]:
    """Collect variation codes that are composition-like but missing components."""
    orphan_codes: Set[str] = set()
    for variation in variations or []:
        code = _variation_code(variation)
        if not code:
            continue
        formato = str(variation.get("formato") or "").strip().upper()
        estrutura = variation.get("estrutura") if isinstance(variation.get("estrutura"), dict) else None
        componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else []
        if formato == "E" and not componentes:
            orphan_codes.add(code)
    return orphan_codes


def _reconcile_orphan_diagnostics(
    existing_orphan_codes: Set[str],
    merged_variations: List[Dict[str, Any]],
    diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    """Reconcile orphan diagnostics against the pre-merge state.

    Some orphans are fixed during merge itself, before the diagnostics helper can
    observe the missing structure. This reconciliation step preserves the fact
    that those variations were orphaned in the original Bling payload.
    """
    if not existing_orphan_codes:
        diagnostics["had_orphan_composition_issue"] = diagnostics.get("had_orphan_composition_issue", False)
        return diagnostics

    merged_with_structure: Set[str] = set()
    for variation in merged_variations:
        code = _variation_code(variation)
        estrutura = variation.get("estrutura") if isinstance(variation.get("estrutura"), dict) else None
        componentes = estrutura.get("componentes") if isinstance(estrutura, dict) else []
        if code and componentes:
            merged_with_structure.add(code)

    repaired = set(diagnostics.get("repaired_orphan_compositions") or [])
    dropped = set(diagnostics.get("dropped_orphan_compositions") or [])

    repaired.update(existing_orphan_codes & merged_with_structure)
    dropped.update(existing_orphan_codes - merged_with_structure)

    diagnostics["repaired_orphan_compositions"] = sorted(repaired)
    diagnostics["dropped_orphan_compositions"] = sorted(dropped)
    diagnostics["had_orphan_composition_issue"] = bool(repaired or dropped)
    return diagnostics


def _normalize_skus(values: Optional[List[str]]) -> Set[str]:
    """Normalize SKU values to uppercase set without empty entries."""
    normalized: Set[str] = set()
    for value in values or []:
        sku = str(value or "").strip().upper()
        if sku:
            normalized.add(sku)
    return normalized


def _deletion_alignment(
    removed_codes: List[str],
    planned_deletions: Optional[List[str]],
) -> Dict[str, List[str]]:
    """Compare removed variation SKUs against planned_deletions from plan builder."""
    removed_set = _normalize_skus(removed_codes)
    planned_set = _normalize_skus(planned_deletions)

    return {
        "planned_deletions": sorted(planned_set),
        "unexpected_removed": sorted(removed_set - planned_set),
        "missing_planned": sorted(planned_set - removed_set),
    }


def _has_deletion_mismatch(alignment: Dict[str, List[str]]) -> bool:
    """Return True when effective removals diverge from planned_deletions."""
    return bool(alignment.get("unexpected_removed") or alignment.get("missing_planned"))


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
        # Note: ncm/cest are inside tributacao (Bling V3), not top-level.
        for field in [
            "variacao", "formato", "nome", "preco", "utilizarDadosDoPai",
            "descricaoCurta", "descricaoComplementar", "marca", "condicao", "categoria",
            "tributacao", "unidade", "unidadeMedida", "dimensoes", "peso", "pesoLiquido", "pesoBruto",
            "largura", "altura", "comprimento", "linkExterno", "observacoes",
        ]:
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

            # Overlay ALL writable fields from the computed/template payload.
            # Skip "id" to preserve the existing Bling variation id.
            for upd_field in _WRITABLE_VARIATION_FIELDS - {"id"}:
                if upd_field in new_var and new_var[upd_field] is not None:
                    updated[upd_field] = new_var[upd_field]

            merged.append(updated)
            del new_map[existing_code]
        else:
            # In sync mode, drop unselected existing variations.
            if not sync_selected_only:
                merged.append(existing_var)
    
    # Add new variations (truly new - not found in existing)
    for new_var in new_map.values():
        if not isinstance(new_var.get("tributacao"), dict):
            new_var["tributacao"] = {}
        if not new_var["tributacao"].get("spedTipoItem"):
            new_var["tributacao"]["spedTipoItem"] = "04"
        merged.append(new_var)

    cleaned = [_sanitize_variation_for_put(v) for v in merged]
    return _dedupe_variations_by_code(cleaned)


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

            # Overlay ALL writable fields from the computed/template payload.
            # Skip "id" to preserve the existing Bling variation id.
            for upd_field in _WRITABLE_VARIATION_FIELDS - {"id"}:
                if upd_field in new_var and new_var[upd_field] is not None:
                    updated[upd_field] = new_var[upd_field]

            merged.append(updated)
        else:
            # Fallback match by code for cases where variacao.nome is missing.
            matched_by_code = next(
                (nv for nv in new_variations if _variation_code(nv) == existing_code and existing_code),
                None,
            )
            if matched_by_code:
                updated = existing_var.copy()
                # Overlay ALL writable fields from the computed/template payload.
                # Skip "id" to preserve the existing Bling variation id.
                for upd_field in _WRITABLE_VARIATION_FIELDS - {"id"}:
                    if upd_field in matched_by_code and matched_by_code[upd_field] is not None:
                        updated[upd_field] = matched_by_code[upd_field]
                merged.append(updated)
            elif not sync_selected_only:
                merged.append(existing_var)
    # Append truly new variations (no name match found)
    for new_var in new_name_map.values():
        if not isinstance(new_var.get("tributacao"), dict):
            new_var["tributacao"] = {}
        if not new_var["tributacao"].get("spedTipoItem"):
            new_var["tributacao"]["spedTipoItem"] = "04"
        merged.append(new_var)
    
    cleaned = [_sanitize_variation_for_put(v) for v in merged]
    return _dedupe_variations_by_code(cleaned)


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


def _fill_missing_variation_structure_with_diagnostics(
    merged_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Backfill composition structure and return structured diagnostics.

    The update flow needs to distinguish between orphan composition variations
    that were automatically rebuilt from the desired payload and those that had
    to be dropped because no valid structure could be recovered.
    """
    structure_by_name: Dict[str, Dict[str, Any]] = {}
    for new_var in new_variations:
        var_name = (new_var.get("variacao") or {}).get("nome", "")
        estrutura = new_var.get("estrutura")
        if var_name and isinstance(estrutura, dict):
            componentes = estrutura.get("componentes") or []
            if componentes:
                structure_by_name[var_name] = estrutura

    rebuilt_variations: List[str] = []
    clean: List[Dict[str, Any]] = []
    dropped_orphan_variations: List[str] = []
    new_codes = {_variation_code(v) for v in new_variations}

    for variation in merged_variations:
        var_name = (variation.get("variacao") or {}).get("nome", "")
        current_estrutura = variation.get("estrutura")
        current_componentes = current_estrutura.get("componentes") if isinstance(current_estrutura, dict) else []

        target_estrutura = structure_by_name.get(var_name)
        if target_estrutura and not current_componentes:
            variation["estrutura"] = target_estrutura
            current_estrutura = variation.get("estrutura")
            current_componentes = current_estrutura.get("componentes") if isinstance(current_estrutura, dict) else []
            rebuilt_code = _variation_code(variation)
            if rebuilt_code:
                rebuilt_variations.append(rebuilt_code)

        componentes = current_estrutura.get("componentes") if isinstance(current_estrutura, dict) else None
        if isinstance(current_estrutura, dict) and not componentes and _variation_code(variation) not in new_codes:
            orphan_code = _variation_code(variation)
            if orphan_code:
                dropped_orphan_variations.append(orphan_code)
            logger.warning(
                f"[MERGE] Dropping orphan composition variation "
                f"'{orphan_code}' — empty estrutura.componentes"
            )
            continue

        clean.append(variation)

    diagnostics = {
        "repaired_orphan_compositions": sorted(set(rebuilt_variations)),
        "dropped_orphan_compositions": sorted(set(dropped_orphan_variations)),
    }
    diagnostics["had_orphan_composition_issue"] = bool(
        diagnostics["repaired_orphan_compositions"] or diagnostics["dropped_orphan_compositions"]
    )
    return clean, diagnostics


def _sanitize_variations_for_retry(
    merged_variations: List[Dict[str, Any]],
    new_variations: List[Dict[str, Any]],
    is_physical: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
    skipped_invalid_compositions: List[str] = []
    for current in merged_variations:
        candidate = _sanitize_variation_for_put(current)
        code = _variation_code(candidate)
        name = (candidate.get("variacao") or {}).get("nome", "")
        desired = desired_by_code.get(code) or desired_by_name.get(name)

        if desired:
            # Overlay ALL writable fields from desired payload (skip "id" to preserve existing id)
            for field in _WRITABLE_VARIATION_FIELDS - {"id"}:
                if field in desired and desired[field] is not None:
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
                if code:
                    skipped_invalid_compositions.append(code)
                continue

        sanitized.append(candidate)

    # Ensure all desired variations exist in retry payload.
    existing_codes = {_variation_code(v) for v in sanitized}
    for code, desired in desired_by_code.items():
        if code and code not in existing_codes:
            sanitized.append(_sanitize_variation_for_put(desired.copy()))

    diagnostics = {
        "retry_skipped_invalid_compositions": sorted(set(skipped_invalid_compositions)),
        "had_retry_sanitization": bool(skipped_invalid_compositions),
    }
    return _dedupe_variations_by_code(sanitized), diagnostics


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


def _build_repair_payload_for_item(
    item: Dict[str, Any],
    sku_cache: Dict[str, Optional[Dict[str, Any]]],
    color_map: Dict[str, str],
    is_physical: bool,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Build a repair payload for non-parent items.

    For VARIATION_PRINTED in virtual stock, repair must rebuild the composition
    structure from the plan dependencies. Returning a structured error allows the
    caller to fail fast with a business-meaningful reason instead of sending an
    invalid simple payload to Bling.
    """
    sku = str(item.get("sku") or "").strip()
    entity = str(item.get("entity") or "").strip().upper()
    computed = item.get("computed_payload_preview")
    if not isinstance(computed, dict):
        computed = {}

    if entity != "VARIATION_PRINTED":
        return _build_variation_item(sku, computed), None

    parent_sku, base_sku = extract_dependencies(item)

    if is_physical:
        if not parent_sku:
            return None, {
                "error_type": "missing_parent_dependency",
                "message": "Variacao impressa sem parent_sku para repair fisico",
                "entity": entity,
            }
        return _build_variation_physical(sku, computed, parent_sku, color_map), None

    if not parent_sku:
        return None, {
            "error_type": "missing_parent_dependency",
            "message": "Variacao impressa sem parent_sku para reconstruir composicao",
            "entity": entity,
        }

    if not base_sku:
        return None, {
            "error_type": "missing_base_dependency",
            "message": "Variacao impressa sem base_sku para reconstruir composicao",
            "entity": entity,
            "parent_sku": parent_sku,
        }

    base_product = sku_cache.get(base_sku) if isinstance(sku_cache, dict) else None
    base_id = base_product.get("id") if isinstance(base_product, dict) else None
    if not base_id:
        return None, {
            "error_type": "missing_base_for_composition",
            "message": "Base da composicao nao encontrada no Bling para repair",
            "entity": entity,
            "parent_sku": parent_sku,
            "base_sku": base_sku,
        }

    payload = _build_variation_with_composition(item, int(base_id), parent_sku, color_map)
    return payload, {
        "repair_action": "orphan_composition_rebuilt",
        "entity": entity,
        "parent_sku": parent_sku,
        "base_sku": base_sku,
        "base_id": int(base_id),
    }


def _get_error_message(error: Exception) -> str:
    """Extract human-readable error message."""
    return str(error) if error else "Erro desconhecido"


def _product_kind_for_entity(entity: Optional[str]) -> Optional[ProductKindEnum]:
    if entity in {"BASE_PARENT", "BASE_VARIATION"}:
        return ProductKindEnum.PLAIN
    if entity in {"PARENT_PRINTED", "VARIATION_PRINTED"}:
        return ProductKindEnum.PRINTED
    return None


async def _sync_snapshot_with_kind(
    client: BlingClient,
    db: Session,
    product_id: Optional[int],
    product_kind: Optional[ProductKindEnum],
    force_direct: bool = False,
) -> None:
    """Refresh local snapshot with explicit business classification when available."""
    if not product_id or product_kind is None:
        return

    product_sync_mode = (settings.PRODUCT_SYNC_MODE or "webhook_first").strip().lower()
    webhook_first = product_sync_mode in {"webhook_first", "webhook"}
    can_defer_to_webhook = webhook_first and settings.WEBHOOKS_ENABLED and not force_direct

    if can_defer_to_webhook and not settings.PRODUCT_SYNC_DIRECT_FALLBACK:
        try:
            ProductSnapshotRepository.upsert_product_kind_hint(
                db=db,
                tenant_id=TENANT_ID,
                bling_product_id=int(product_id),
                product_kind=product_kind,
            )
            db.commit()
            logger.info(
                "[SNAPSHOT] Deferred full sync to webhook pipeline for product_id=%s mode=%s",
                int(product_id),
                product_sync_mode,
            )
            return
        except Exception as exc:
            logger.warning(
                "[SNAPSHOT] Failed to persist webhook-first hint for product_id=%s: %s",
                int(product_id),
                exc,
            )

    try:
        detail = await client.get_product(int(product_id))
        if detail:
            ProductSnapshotRepository.upsert_product_detail(
                db,
                TENANT_ID,
                detail,
                product_kind=product_kind,
            )
            db.commit()
    except Exception as exc:
        logger.warning(
            f"[SNAPSHOT] Failed to refresh local snapshot for product_id={product_id}: {exc}"
        )


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
    if bool((plan.get("options") or {}).get("execute_async", False)):
        token = BlingTokenRepository.get_by_tenant(db, TENANT_ID)
        if not token:
            raise HTTPException(status_code=401, detail="Bling token not configured")

        try:
            from app.workers.tasks import process_plan_execution_task

            task = process_plan_execution_task.delay(plan)
            return {
                "status": "queued",
                "runner": "celery",
                "task_id": task.id,
                "message": "Execução do plano enfileirada com sucesso.",
                "status_url": f"/plans/execute/status/{task.id}",
                "sync_mode": settings.PRODUCT_SYNC_MODE,
            }
        except Exception as exc:
            logger.error("plan_execution_queue_dispatch_failed error=%s", str(exc), exc_info=True)
            raise HTTPException(status_code=503, detail="Fila indisponível para execução assíncrona")

    client = await _get_bling_client(db)
    if not client:
        raise HTTPException(status_code=401, detail="Bling token not configured")

    items = plan.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="Plan has no items")

    stock_type = (plan.get("options") or {}).get("stock_type", "virtual")
    is_physical = stock_type == "physical"
    strict_planned_deletions = bool(
        (plan.get("options") or {}).get("strict_planned_deletions", False)
    )
    force_direct_product_sync = bool(
        (plan.get("options") or {}).get("force_direct_product_sync", False)
    )
    
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
        product_kind = _product_kind_for_entity(item.get("entity"))
        computed = item.get("computed_payload_preview") or {}
        payload = _prepare_base_payload(sku, computed.get("nome"), computed)
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
                    base_variations.append(_sanitize_variation_for_put(var))
        
        payload["variacoes"] = base_variations
        logger.debug(f"Creating base {sku}")
        
        created_id, create_error = await create_product_with_error(client, payload)
        if created_id:
            base_ids[sku] = created_id
            await _sync_snapshot_with_kind(
                client,
                db,
                created_id,
                product_kind,
                force_direct=force_direct_product_sync,
            )
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "CREATE",
                "id": created_id,
                "status": "success",
                "variations_count": len(base_variations),
            })
        else:
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "CREATE",
                "status": "failed",
                "error": create_error or "Falha ao criar base no Bling",
            })

    # ========== STEP 1b: UPDATE BASE_PARENT (plain products already in Bling) ==========
    for item in items:
        if item.get("entity") != "BASE_PARENT" or item.get("action") != "UPDATE":
            continue

        sku = item["sku"]
        product_kind = _product_kind_for_entity(item.get("entity"))

        # Resolve the existing product ID (plan carries it in existing_product when available)
        existing_product_data: Dict[str, Any] = item.get("existing_product") or {}
        existing_id: Optional[int] = existing_product_data.get("id") or get_id_from_cache(sku)

        if not existing_id:
            existing_id = await fetch_id_by_sku(client, sku)

        if not existing_id:
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "UPDATE",
                "status": "failed",
                "error": "Produto não encontrado no Bling",
            })
            continue

        try:
            # Fetch full product to preserve read-only metadata (images, etc.)
            full_resp = await client.get(f"/produtos/{existing_id}")
            full_data = (full_resp or {}).get("data", {})
            existing_variations = full_data.get("variacoes", [])

            # Build parent payload reusing the same helper as printed UPDATE,
            # so ALL template fields from computed_payload_preview are applied.
            payload = _prepare_parent_payload(item, full_data)
            payload["formato"] = "V"  # plain parent is always formato V

            # Build desired variation payloads using the same helper as STEP 1 CREATE.
            # This guarantees identical structure (variacao.nome, ncm, cest, etc.).
            new_variations: List[Dict[str, Any]] = []
            for var_item in items:
                if var_item.get("entity") != "BASE_VARIATION":
                    continue
                var_deps = var_item.get("hard_dependencies") or []
                if not var_deps or var_deps[0] != sku:
                    continue
                var_sku = var_item.get("sku", "")
                var_computed = var_item.get("computed_payload_preview") or {}
                var_entry = _build_variation_item(
                    var_sku, var_computed, formato="S",
                    variacao=var_computed.get("variacao") or {},
                )
                # Also carry description fields from computed (template-derived)
                for desc_field in ["descricaoCurta", "descricaoComplementar"]:
                    if desc_field in var_computed:
                        var_entry[desc_field] = var_computed[desc_field]
                new_variations.append(var_entry)

            # Merge: for existing variations preserve their IDs/images/variacao.nome
            # and overlay only the mutable computed fields (nome, preco, descriptions).
            existing_by_code = {
                _variation_code(v): v for v in existing_variations if _variation_code(v)
            }
            merged: List[Dict[str, Any]] = []
            new_codes = {_variation_code(v) for v in new_variations if _variation_code(v)}

            for new_var in new_variations:
                code = _variation_code(new_var)
                if code and code in existing_by_code:
                    # Start from existing (preserves id, images)
                    merged_var = existing_by_code[code].copy()
                    # Overlay ALL writable fields from the computed/template payload
                    # so that marca, peso, dimensoes, tributacao, unidade, etc. are applied.
                    # Skip "id" to preserve the existing Bling variation id.
                    for upd_field in _WRITABLE_VARIATION_FIELDS - {"id"}:
                        if upd_field in new_var and new_var[upd_field] is not None:
                            merged_var[upd_field] = new_var[upd_field]
                    # Remove utilizarDadosDoPai if accidentally set
                    merged_var.pop("utilizarDadosDoPai", None)
                    merged.append(merged_var)
                else:
                    # Brand-new variation not yet in Bling
                    merged.append(new_var)

            # Preserve existing variations outside the selected set
            for existing_var in existing_variations:
                code = _variation_code(existing_var)
                if code and code not in new_codes:
                    merged.append(existing_var)

            payload["variacoes"] = [
                _sanitize_variation_for_put(v)
                for v in _dedupe_variations_by_code(merged)
            ]

            logger.info(f"[UPDATE BASE_PARENT] {sku} (id={existing_id}), {len(payload['variacoes'])} variation(s)")
            _log_variation_payload_shape("UPDATE_BASE_PARENT", sku, payload.get("variacoes") or [])
            await client.put(f"/produtos/{existing_id}", payload)
            base_ids[sku] = existing_id
            await _sync_snapshot_with_kind(
                client, db, existing_id, product_kind, force_direct=force_direct_product_sync
            )
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "UPDATE",
                "id": existing_id,
                "status": "success",
                "variations_count": len(payload["variacoes"]),
            })
        except Exception as e:
            logger.error(f"[UPDATE BASE_PARENT] Error updating {sku}: {e}", exc_info=True)
            results.append({
                "sku": sku,
                "entity": "BASE_PARENT",
                "action": "UPDATE",
                "status": "failed",
                "error": _get_error_message(e),
                "target_id": existing_id,
            })

    # ========== STEP 2: CREATE PRODUTO (printed parent with variations) ==========
    for item in items:
        if item.get("entity") != "PARENT_PRINTED" or item.get("action") != "CREATE":
            continue

        sku = item["sku"]
        planned_deletions = item.get("planned_deletions") or []
        product_kind = _product_kind_for_entity(item.get("entity"))
        payload = _prepare_parent_payload(item)
        payload["variacoes"] = [
            _sanitize_variation_for_put(v)
            for v in (children_map.get(sku, []) or [])
        ]
        
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
                        existing_orphan_codes = _orphan_composition_codes(existing_variations)
                        existing_codes = _variation_codes_set(existing_variations)
                        selected_codes = _variation_codes_set(payload.get("variacoes", []))

                        merged_variations = _merge_variations(
                            existing_variations,
                            payload.get("variacoes", []),
                            sync_selected_only=True,
                        )
                        merged_variations, merge_diagnostics = _fill_missing_variation_structure_with_diagnostics(
                            merged_variations,
                            payload.get("variacoes", []),
                        )
                        merge_diagnostics = _reconcile_orphan_diagnostics(
                            existing_orphan_codes,
                            merged_variations,
                            merge_diagnostics,
                        )
                        merged_codes = _variation_codes_set(merged_variations)
                        removed_codes = sorted(existing_codes - merged_codes)
                        deletion_alignment = _deletion_alignment(removed_codes, planned_deletions)
                        existing_ids_by_code = _variation_ids_by_code(existing_variations)
                        removed_deleted_count = 0
                        removed_delete_failed: List[str] = []

                        if _has_deletion_mismatch(deletion_alignment):
                            logger.warning(
                                f"[SYNC] {sku}: deletion alignment mismatch "
                                f"unexpected_removed={deletion_alignment['unexpected_removed']} "
                                f"missing_planned={deletion_alignment['missing_planned']}"
                            )

                        if strict_planned_deletions and _has_deletion_mismatch(deletion_alignment):
                            results.append({
                                "sku": sku,
                                "entity": "PARENT_PRINTED",
                                "action": "UPDATE",
                                "id": candidate_parent_id,
                                "status": "failed",
                                "error": "Strict planned deletions mismatch",
                                "planned_deletions": deletion_alignment["planned_deletions"],
                                "unexpected_removed_variations": deletion_alignment["unexpected_removed"],
                                "missing_planned_deletions": deletion_alignment["missing_planned"],
                                "recovery_mode": "create_conflict_updated_existing_parent",
                            })
                            recovered = True
                            continue

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
                        retry_payload["variacoes"] = [
                            _sanitize_variation_for_put(v)
                            for v in merged_variations
                        ]

                        await client.put(f"/produtos/{candidate_parent_id}", retry_payload)
                        await _sync_snapshot_with_kind(
                            client,
                            db,
                            candidate_parent_id,
                            product_kind,
                            force_direct=force_direct_product_sync,
                        )

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
                            "planned_deletions": deletion_alignment["planned_deletions"],
                            "unexpected_removed_variations": deletion_alignment["unexpected_removed"],
                            "missing_planned_deletions": deletion_alignment["missing_planned"],
                            "repaired_orphan_compositions": merge_diagnostics.get("repaired_orphan_compositions", []),
                            "dropped_orphan_compositions": merge_diagnostics.get("dropped_orphan_compositions", []),
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
        planned_deletions = item.get("planned_deletions") or []
        product_kind = _product_kind_for_entity(item.get("entity"))
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
            existing_orphan_codes = _orphan_composition_codes(existing_variations)
            new_variations = children_map.get(sku, [])
            existing_codes = _variation_codes_set(existing_variations)
            selected_codes = _variation_codes_set(new_variations)
            orphan_diagnostics: Dict[str, Any] = {
                "repaired_orphan_compositions": [],
                "dropped_orphan_compositions": [],
                "retry_skipped_invalid_compositions": [],
            }
            
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
            merged_variations, merge_diagnostics = _fill_missing_variation_structure_with_diagnostics(
                merged_variations,
                new_variations,
            )
            merge_diagnostics = _reconcile_orphan_diagnostics(
                existing_orphan_codes,
                merged_variations,
                merge_diagnostics,
            )
            orphan_diagnostics.update(merge_diagnostics)
            merged_codes = _variation_codes_set(merged_variations)
            removed_codes = sorted(existing_codes - merged_codes)
            deletion_alignment = _deletion_alignment(removed_codes, planned_deletions)
            existing_ids_by_code = _variation_ids_by_code(existing_variations)
            removed_deleted_count = 0
            removed_delete_failed: List[str] = []

            if _has_deletion_mismatch(deletion_alignment):
                logger.warning(
                    f"[SYNC] {sku}: deletion alignment mismatch "
                    f"unexpected_removed={deletion_alignment['unexpected_removed']} "
                    f"missing_planned={deletion_alignment['missing_planned']}"
                )

            if strict_planned_deletions and _has_deletion_mismatch(deletion_alignment):
                results.append({
                    "sku": sku,
                    "entity": "PARENT_PRINTED",
                    "action": "UPDATE",
                    "id": existing_id,
                    "status": "failed",
                    "error": "Strict planned deletions mismatch",
                    "planned_deletions": deletion_alignment["planned_deletions"],
                    "unexpected_removed_variations": deletion_alignment["unexpected_removed"],
                    "missing_planned_deletions": deletion_alignment["missing_planned"],
                })
                continue

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
            if orphan_diagnostics.get("had_orphan_composition_issue"):
                orphan_warning = orphan_warning or {
                    "error_type": "orphan_composition_variations",
                    "bling_product_id": existing_id,
                }
                orphan_warning.update({
                    "repaired_orphan_compositions": orphan_diagnostics.get("repaired_orphan_compositions", []),
                    "dropped_orphan_compositions": orphan_diagnostics.get("dropped_orphan_compositions", []),
                })
                if orphan_diagnostics.get("repaired_orphan_compositions"):
                    orphan_warning["repair_action"] = "orphan_composition_rebuilt"

            # Pass existing product to preserve images/links
            payload = _prepare_parent_payload(item, existing_product_data)
            payload["variacoes"] = [
                _sanitize_variation_for_put(v)
                for v in merged_variations
            ]
            _log_variation_payload_shape("UPDATE_PARENT_PRINTED", sku, payload.get("variacoes") or [])
            try:
                resp = await client.put(f"/produtos/{existing_id}", payload)
            except Exception as first_put_error:
                # One automatic retry with sanitized variations before surfacing error.
                retry_variations, retry_diagnostics = _sanitize_variations_for_retry(
                    merged_variations=merged_variations,
                    new_variations=new_variations,
                    is_physical=is_physical,
                )
                orphan_diagnostics.update(retry_diagnostics)
                if retry_diagnostics.get("retry_skipped_invalid_compositions"):
                    orphan_warning = orphan_warning or {
                        "error_type": "orphan_composition_variations",
                        "bling_product_id": existing_id,
                    }
                    orphan_warning["retry_skipped_invalid_compositions"] = retry_diagnostics.get(
                        "retry_skipped_invalid_compositions", []
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
                await _sync_snapshot_with_kind(
                    client,
                    db,
                    existing_id,
                    product_kind,
                    force_direct=force_direct_product_sync,
                )
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
                    "planned_deletions": deletion_alignment["planned_deletions"],
                    "unexpected_removed_variations": deletion_alignment["unexpected_removed"],
                    "missing_planned_deletions": deletion_alignment["missing_planned"],
                    "repaired_orphan_compositions": orphan_diagnostics.get("repaired_orphan_compositions", []),
                    "dropped_orphan_compositions": orphan_diagnostics.get("dropped_orphan_compositions", []),
                    "retry_skipped_invalid_compositions": orphan_diagnostics.get("retry_skipped_invalid_compositions", []),
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
                    "repaired_orphan_compositions": orphan_diagnostics.get("repaired_orphan_compositions", []),
                    "dropped_orphan_compositions": orphan_diagnostics.get("dropped_orphan_compositions", []),
                    "retry_skipped_invalid_compositions": orphan_diagnostics.get("retry_skipped_invalid_compositions", []),
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
                "repaired_orphan_compositions": orphan_diagnostics.get("repaired_orphan_compositions", []) if 'orphan_diagnostics' in locals() else [],
                "dropped_orphan_compositions": orphan_diagnostics.get("dropped_orphan_compositions", []) if 'orphan_diagnostics' in locals() else [],
                "retry_skipped_invalid_compositions": orphan_diagnostics.get("retry_skipped_invalid_compositions", []) if 'orphan_diagnostics' in locals() else [],
            }
            # Keep context if orphan cleanup was attempted in this run.
            if 'orphan_warning' in locals() and orphan_warning:
                result_item.update(orphan_warning)
            results.append(result_item)

    # No STEP 4 needed - all variations handled in STEP 2/3

    # ========== STEP 5: Register NOOP items (no action needed) ==========
    # Add result entries for items that were skipped because they were already
    # up-to-date, so the frontend can show the complete picture.
    processed_skus = {r["sku"] for r in results}
    for item in items:
        sku = item.get("sku")
        if not sku or sku in processed_skus:
            continue
        action = item.get("action", "")
        entity = item.get("entity", "")
        if action == "NOOP":
            results.append({
                "sku": sku,
                "entity": entity,
                "action": "NOOP",
                "status": "noop",
                "message": item.get("message", "Sem alteração necessária"),
            })
        elif action == "UPDATE" and entity == "BASE_VARIATION":
            # BASE_VARIATION UPDATE items are patched inline as part of their parent's PUT.
            # Register them as success so the count reflects all touched items.
            results.append({
                "sku": sku,
                "entity": entity,
                "action": "UPDATE",
                "status": "success",
                "message": "Atualizado como parte do produto pai",
            })

    await client.client.aclose()
    
    # Summary
    success = [r for r in results if r.get("status") in ("success", "noop")]
    created_success_items = [
        r for r in results
        if r.get("status") == "success" and r.get("action") == "CREATE"
    ]
    created_variations = sum(int(r.get("variations_count") or 0) for r in created_success_items)
    created_items_total = len(created_success_items) + created_variations

    updated_items = [
        r for r in results
        if r.get("status") == "success" and r.get("action") == "UPDATE"
    ]
    noop_items = [r for r in results if r.get("status") == "noop"]
    repaired_orphan_compositions = sorted({
        code
        for r in results
        for code in (r.get("repaired_orphan_compositions") or [])
    })
    dropped_orphan_compositions = sorted({
        code
        for r in results
        for code in (r.get("dropped_orphan_compositions") or [])
    })
    retry_skipped_invalid_compositions = sorted({
        code
        for r in results
        for code in (r.get("retry_skipped_invalid_compositions") or [])
    })
    return {
        "status": "completed",
        "total_items": len(items),
        "results": results,
        "summary": {
            "total": len(results),
            "success": len(success),
            "created_products": len(created_success_items),
            "created_variations": created_variations,
            "created_items": created_items_total,
            "updated_items": len(updated_items),
            "noop_items": len(noop_items),
            "failed": len([r for r in results if r.get("status") == "failed"]),
            "repaired_orphan_compositions": repaired_orphan_compositions,
            "dropped_orphan_compositions": dropped_orphan_compositions,
            "retry_skipped_invalid_compositions": retry_skipped_invalid_compositions,
        }
    }


@router.get("/execute/status/{task_id}")
async def get_execute_plan_status(task_id: str):
    """Return Celery task status and result for async plan execution."""
    task_result = AsyncResult(task_id, app=celery_app)
    state = str(task_result.state or "PENDING")

    if state == "SUCCESS":
        payload = task_result.result if isinstance(task_result.result, dict) else {"result": task_result.result}
        return {
            "status": "completed",
            "task_id": task_id,
            "state": state,
            **payload,
        }

    if state == "FAILURE":
        return {
            "status": "failed",
            "task_id": task_id,
            "state": state,
            "error": str(task_result.result),
        }

    return {
        "status": "running" if state in {"STARTED", "RETRY"} else "queued",
        "task_id": task_id,
        "state": state,
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
    """Repair products that failed in UPDATE step by updating in-place (idempotent).
    
    New strategy: Update existing products in-place without deletion. Only deletes as last resort.
    Returns repaired_in_place status for successful repairs.
    """
    results = []
    processed_target_ids = set()
    
    try:
        client = await _get_bling_client(db)
        if not client:
            raise HTTPException(status_code=401, detail="Bling token not configured")

        plan = payload.get("plan") or {}
        failed_update_skus = set(payload.get("failed_update_skus") or [])

        if not failed_update_skus:
            raise HTTPException(status_code=400, detail="Nenhum SKU de falha informado para reparo")

        items = plan.get("items", [])
        if not items:
            raise HTTPException(status_code=400, detail="Plano inválido: sem itens")

        candidates = [
            item for item in items
            if item.get("action") == "UPDATE"
            and item.get("sku") in failed_update_skus
        ]

        if not candidates:
            await client.client.aclose()
            return {
                "results": [],
                "summary": {
                    "requested": len(failed_update_skus),
                    "processed": 0,
                    "repaired": 0,
                    "failed": 0,
                }
            }

        # Build children map for parent products (variations)
        stock_type = (plan.get("options") or {}).get("stock_type", "virtual")
        is_physical = stock_type == "physical"
        candidate_parent_skus = {
            item.get("sku") for item in candidates
            if item.get("entity") in {"PARENT_PRINTED", "BASE_PARENT"} and item.get("sku")
        }
        relevant_items: List[Dict[str, Any]] = []
        for item in items:
            sku = item.get("sku")
            if sku in failed_update_skus:
                relevant_items.append(item)
                continue
            if item.get("entity") == "VARIATION_PRINTED":
                hard = item.get("hard_dependencies") or []
                parent_sku = hard[0] if hard else None
                if parent_sku in candidate_parent_skus:
                    relevant_items.append(item)

        children_map: Dict[str, List[Dict[str, Any]]] = {}
        sku_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        color_map: Dict[str, str] = {}
        try:
            all_skus = _collect_all_skus(relevant_items)
            from app.api.plans import _check_bling_products_bulk
            sku_cache = await _check_bling_products_bulk(client, list(all_skus))
            
            color_map = _build_color_map(plan, db)
            if is_physical:
                children_map = _build_children_map_physical(relevant_items, color_map)
            else:
                children_map = _build_children_map(relevant_items, sku_cache, color_map)
        except Exception as prep_error:
            logger.warning(
                "[REPAIR] Pre-processing failed; continuing without full children map: %s",
                _get_error_message(prep_error),
            )
            children_map = {}

        # Process each failed SKU with repair-first strategy
        for item in candidates:
            try:
                sku = item.get("sku")
                entity = item.get("entity", "UNKNOWN")
                target_id = item.get("force_update_id")
                
                logger.info(f"[REPAIR] Processing failed UPDATE for sku={sku}, entity={entity}, target_id={target_id}")

                # Resolve target_id if not provided
                if not target_id:
                    try:
                        target_id = await fetch_id_by_sku(client, sku)
                    except Exception as lookup_error:
                        logger.warning(f"[REPAIR] Could not lookup {sku}: {_get_error_message(lookup_error)}")
                        target_id = None

                if not target_id:
                    results.append({
                        "sku": sku,
                        "status": "failed",
                        "error": "Produto não encontrado no Bling",
                    })
                    continue

                # Skip if already processed in this batch (idempotency)
                if target_id in processed_target_ids:
                    results.append({
                        "sku": sku,
                        "status": "skipped",
                        "target_id": target_id,
                        "reason": "Mesmo produto já processado nesta operação",
                    })
                    continue
                processed_target_ids.add(target_id)

                # PRIMARY STRATEGY: Repair in-place via PUT
                try:
                    logger.info(f"[REPAIR] Fetching existing product {sku} (id={target_id})")
                    existing_resp = await client.get(f"/produtos/{target_id}")
                    existing_product_data = existing_resp.get("data", {})
                    
                    if not isinstance(existing_product_data, dict):
                        raise ValueError(f"Invalid product data structure from Bling for id={target_id}")
                    
                    # Build repair payload based on entity type
                    if entity in ["PARENT_PRINTED", "BASE_PARENT"]:
                        # Parent product with variations
                        repair_payload = _prepare_parent_payload(item, existing_product_data)
                        repair_payload["variacoes"] = [
                            _sanitize_variation_for_put(v)
                            for v in (children_map.get(sku, []) or [])
                        ]
                        logger.info(f"[REPAIR] Built parent repair payload with {len(repair_payload.get('variacoes', []))} variations")
                    else:
                        repair_payload, repair_context = _build_repair_payload_for_item(
                            item=item,
                            sku_cache=sku_cache,
                            color_map=color_map,
                            is_physical=is_physical,
                        )
                        if repair_payload is None:
                            logger.warning(
                                "[REPAIR] Cannot rebuild payload for %s: %s",
                                sku,
                                repair_context,
                            )
                            failure_item = {
                                "sku": sku,
                                "entity": entity,
                                "status": "failed",
                                "target_id": target_id,
                                "error": (repair_context or {}).get("message") or "Payload de repair invalido",
                            }
                            if repair_context:
                                failure_item.update(repair_context)
                            results.append(failure_item)
                            continue

                        logger.info(
                            "[REPAIR] Built %s repair payload for %s",
                            (repair_context or {}).get("repair_action", "simple_product"),
                            sku,
                        )

                    # Execute in-place repair via PUT
                    logger.info(f"[REPAIR] Executing PUT repair for {sku} (id={target_id})")
                    await client.put(f"/produtos/{target_id}", repair_payload)
                    
                    success_item = {
                        "sku": sku,
                        "entity": entity,
                        "status": "success",
                        "action": "repaired_in_place",
                        "target_id": target_id,
                        "message": "Produto reparado com sucesso no mesmo ID",
                    }
                    if entity not in ["PARENT_PRINTED", "BASE_PARENT"] and repair_context:
                        success_item.update(repair_context)
                    results.append(success_item)
                    logger.info(f"[REPAIR] Successfully repaired {sku} (id={target_id})")
                    
                except Exception as repair_error:
                    # FALLBACK: If PUT fails, try DELETE+CREATE as last resort
                    logger.warning(
                        f"[REPAIR] In-place repair failed for {sku} (id={target_id}), attempting delete+recreate: {_get_error_message(repair_error)}"
                    )
                    
                    try:
                        # Try to delete
                        try:
                            await client.delete(f"/produtos/{target_id}")
                            logger.info(f"[REPAIR] Deleted {sku} (id={target_id}) successfully")
                        except Exception as delete_error:
                            logger.warning(f"[REPAIR] Delete failed for {sku} (id={target_id}): {_get_error_message(delete_error)}")
                            # If delete fails, give up
                            raise delete_error
                        
                        # Try to recreate
                        if entity in ["PARENT_PRINTED", "BASE_PARENT"]:
                            create_payload = _prepare_parent_payload(item)
                            create_payload["variacoes"] = [
                                _sanitize_variation_for_put(v)
                                for v in (children_map.get(sku, []) or [])
                            ]
                        else:
                            computed = item.get("computed_payload_preview") or {}
                            create_payload = _build_variation_item(sku, computed)
                        
                        created_id = await create_product(client, create_payload)
                        if created_id:
                            results.append({
                                "sku": sku,
                                "entity": entity,
                                "status": "success",
                                "action": "recreated_after_delete",
                                "old_id": target_id,
                                "new_id": created_id,
                                "message": "Produto excluído e recriado com novo ID (PUT falhou)",
                            })
                            logger.info(f"[REPAIR] Recreated {sku} with new id={created_id} after delete")
                        else:
                            results.append({
                                "sku": sku,
                                "status": "failed",
                                "error": f"Produto excluído mas recriação falhou: {_get_error_message(repair_error)}",
                                "old_id": target_id,
                            })
                    except Exception as fallback_error:
                        results.append({
                            "sku": sku,
                            "status": "failed",
                            "error": f"Reparo falhou (PUT) e fallback (DELETE+CREATE) também: {_get_error_message(fallback_error)}",
                            "target_id": target_id,
                        })
                        logger.error(
                            f"[REPAIR] Both repair and fallback failed for {sku} (id={target_id}): {_get_error_message(fallback_error)}",
                            exc_info=True
                        )
            
            except Exception as item_error:
                # Unexpected error for this item - log and continue
                logger.error(
                    f"[REPAIR] Unexpected error processing {item.get('sku')}: {_get_error_message(item_error)}",
                    exc_info=True
                )
                results.append({
                    "sku": item.get("sku", "UNKNOWN"),
                    "status": "failed",
                    "error": f"Erro inesperado: {_get_error_message(item_error)}",
                })

        # Summary
        success_count = len([r for r in results if r.get("status") == "success"])
        failed_count = len([r for r in results if r.get("status") == "failed"])
        rebuilt_orphan_compositions = sorted({
            r.get("sku")
            for r in results
            if r.get("repair_action") == "orphan_composition_rebuilt" and r.get("sku")
        })
        blocked_orphan_compositions = sorted({
            r.get("sku")
            for r in results
            if r.get("error_type") in {"missing_parent_dependency", "missing_base_dependency", "missing_base_for_composition"}
            and r.get("sku")
        })
        
        return {
            "results": results,
            "summary": {
                "requested": len(failed_update_skus),
                "processed": len(results),
                "repaired": success_count,
                "failed": failed_count,
                "rebuilt_orphan_compositions": rebuilt_orphan_compositions,
                "blocked_orphan_compositions": blocked_orphan_compositions,
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as outer_error:
        # Catch any unhandled exception and return structured error
        logger.error(
            f"[REPAIR] Unexpected outer exception in recreate_failed_updates: {_get_error_message(outer_error)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao reparar produtos: {_get_error_message(outer_error)}"
        )
    finally:
        try:
            await client.client.aclose()
        except Exception as close_error:
            logger.warning(f"[REPAIR] Error closing client: {_get_error_message(close_error)}")


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
                    variacoes.append(_sanitize_variation_for_put(var))
                
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
                        payload["variacoes"] = [
                            _sanitize_variation_for_put(v)
                            for v in new_variacoes
                        ]
                        
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
                    payload["variacoes"] = [
                        _sanitize_variation_for_put(v)
                        for v in variacoes
                    ]
                    
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
