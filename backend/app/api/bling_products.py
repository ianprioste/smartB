"""Router for Bling product search endpoints."""
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.infra.bling_client import BlingClient
from app.models.schemas import BlingProductSearchResponse, BlingProductDetailResponse, BlingProductSearchItem
from app.repositories.bling_token_repo import BlingTokenRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bling/products", tags=["bling"])

# Fixed tenant ID for Sprint 1 (single-tenant)
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("/search", response_model=BlingProductSearchResponse)
async def search_products(
    q: str = Query(..., min_length=1, description="Search query (name or SKU)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search_by: Optional[str] = Query(None, description="Search by 'name' or 'sku'. Auto-detect if not specified."),
    db: Session = Depends(get_db),
):
    """
    Search products in Bling.

    - **q**: Search query (product name or SKU/codigo).
    - **page**: Page number (1-indexed).
    - **limit**: Items per page (1-100).
    - **search_by**: Force search by 'name' or 'sku'. If not specified, auto-detects based on query format.
    
    **Auto-detection:** Queries that are short, uppercase, and have no spaces are treated as SKU.
    """
    logger.info("search_products", extra={
        "query": q,
        "page": page,
        "limit": limit,
        "search_by": search_by,
    })
    
    # Get Bling OAuth2 token from database
    bling_token = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not bling_token:
        raise HTTPException(
            status_code=401,
            detail="Nenhum token OAuth2 encontrado. Por favor, autentique-se primeiro em /auth/callback."
        )
    
    # Callback to save refreshed token back to database
    def save_refreshed_token(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info("token_refreshed_and_saved", extra={"tenant_id": str(DEFAULT_TENANT_ID)})
    
    # Initialize Bling client with token and callback
    bling_client = BlingClient(
        access_token=bling_token.access_token,
        refresh_token=bling_token.refresh_token,
        token_expires_at=bling_token.expires_at,
        on_token_refresh=save_refreshed_token,
    )
    
    try:
        # Search in Bling (returns paginated results)
        results = await bling_client.search_products(q, page=page, limit=limit)
        
        # Extract items
        items = []
        total = 0
        if isinstance(results, dict):
            data = results.get("data", [])
            total = results.get("total", len(data)) if isinstance(results, dict) else len(data)
            
            for product in data:
                items.append(BlingProductSearchItem(
                    id=product.get("id"),
                    codigo=product.get("codigo", ""),
                    nome=product.get("nome", ""),
                    formato=product.get("formato"),
                    situacao=product.get("situacao"),
                ))
        
        return BlingProductSearchResponse(
            total=total,
            page=page,
            limit=limit,
            items=items,
        )
    
    except Exception as e:
        error_msg = str(e)
        logger.error("bling_search_failed", extra={
            "query": q,
            "error": error_msg,
            "error_type": type(e).__name__,
        })
        
        # Import here to avoid circular dependency
        from app.infra.bling_client import BlingRefreshTokenExpiredError
        
        # Parse error to provide better message
        if isinstance(e, BlingRefreshTokenExpiredError) or "Refresh token expired" in error_msg:
            detail_msg = "Token do Bling expirado. É necessário autenticar novamente. Acesse /auth/bling/connect para obter novo token."
            status_code = 401
            code = "BLING_TOKEN_EXPIRED"
        elif "404" in error_msg or "Not Found" in error_msg:
            detail_msg = "Nenhum produto encontrado no Bling com este nome ou SKU. Verifique se o produto existe no Bling."
            status_code = 404
            code = "BLING_PRODUCT_NOT_FOUND"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            detail_msg = "Erro de autenticação com Bling. Token pode estar inválido. Tente autenticar novamente em /auth/bling/connect."
            status_code = 401
            code = "BLING_UNAUTHORIZED"
        elif "429" in error_msg:
            detail_msg = "Limite de requisições excedido. Tente novamente em alguns minutos."
            status_code = 429
            code = "BLING_RATE_LIMITED"
        else:
            detail_msg = f"Erro ao buscar produtos no Bling: {error_msg}"
            status_code = 500
            code = "BLING_SEARCH_FAILED"
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": code,
                "message": detail_msg,
                "details": error_msg,
                "needs_reauth": isinstance(e, BlingRefreshTokenExpiredError) or "Refresh token expired" in error_msg,
            },
        )


@router.get("/{product_id}", response_model=BlingProductDetailResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a Bling product.

    - **product_id**: Bling product ID.
    """
    logger.info("get_product", extra={
        "product_id": product_id,
    })
    
    # Get Bling OAuth2 token from database
    bling_token = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not bling_token:
        raise HTTPException(
            status_code=401,
            detail="Nenhum token OAuth2 encontrado. Por favor, autentique-se primeiro em /auth/callback."
        )
    
    # Callback to save refreshed token back to database
    def save_refreshed_token(access_token: str, refresh_token: str, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info("token_refreshed_and_saved", extra={"tenant_id": str(DEFAULT_TENANT_ID)})
    
    # Initialize Bling client with token and callback
    bling_client = BlingClient(
        access_token=bling_token.access_token,
        refresh_token=bling_token.refresh_token,
        token_expires_at=bling_token.expires_at,
        on_token_refresh=save_refreshed_token,
    )
    
    try:
        product = await bling_client.get_product(product_id)
        
        return BlingProductDetailResponse(
            id=product.get("id"),
            codigo=product.get("codigo", ""),
            nome=product.get("nome", ""),
            formato=product.get("formato"),
            situacao=product.get("situacao"),
            descricao=product.get("descricao"),
            preco=product.get("preco"),
            categoria_id=product.get("categoria", {}).get("id"),
        )
    
    except Exception as e:
        logger.error("bling_product_fetch_failed", extra={
            "product_id": product_id,
            "error": str(e),
        })
        raise HTTPException(
            status_code=404,
            detail={
                "code": "BLING_PRODUCT_NOT_FOUND",
                "message": f"Product {product_id} not found in Bling",
                "details": str(e),
            },
        )
