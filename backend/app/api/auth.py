"""Authentication endpoints for Bling OAuth2."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import httpx
import uuid
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
import base64
from typing import Dict, Any

from app.infra.db import get_db
from app.infra.logging import get_logger
from app.models.schemas import BlingAuthUrlResponse, BlingCallbackRequest, TokenAuthResponse
from app.repositories.bling_token_repo import BlingTokenRepository
from app.settings import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Store state for CSRF protection (in production, use secure session storage)
_oauth_states = {}


def _get_retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    """Resolve retry delay from Retry-After or fallback short backoff."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        retry_after = retry_after.strip()
        try:
            delay = float(retry_after)
            if delay > 0:
                return min(delay, 8.0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    from datetime import timezone
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                now_utc = datetime.utcnow().replace(tzinfo=retry_at.tzinfo)
                delay = (retry_at - now_utc).total_seconds()
                if delay > 0:
                    return min(delay, 8.0)
            except Exception:
                pass

    try:
        payload = response.json()
        if isinstance(payload, dict):
            payload_retry = payload.get("retry_after") or payload.get("retryAfter")
            if payload_retry is not None:
                delay = float(payload_retry)
                if delay > 0:
                    return min(delay, 8.0)
    except Exception:
        pass

    return min(1.5 * (attempt + 1), 5.0)


def _resolve_redirect_uri(request: Request) -> str:
    """Resolve OAuth callback URL dynamically, unless explicitly configured."""
    if settings.BLING_REDIRECT_URI:
        return settings.BLING_REDIRECT_URI

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    prefix = request.headers.get("x-forwarded-prefix", "").strip()

    if prefix and not prefix.startswith("/"):
        prefix = f"/{prefix}"
    prefix = prefix.rstrip("/")

    return f"{scheme}://{host}{prefix}/auth/bling/callback"


@router.get("/bling/connect")
async def bling_connect_redirect(request: Request):
    """
    Redirect directly to Bling OAuth2 authorization page.
    
    This is the easiest way to re-authenticate:
    Just visit this URL in your browser and you'll be redirected to Bling.
    """
    
    state = str(uuid.uuid4())
    redirect_uri = _resolve_redirect_uri(request)
    _oauth_states[state] = {
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "redirect_uri": redirect_uri,
    }
    
    # Build auth URL with proper URL encoding
    auth_params = {
        "client_id": settings.BLING_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read write",
        "state": state,
    }
    auth_url = f"{settings.BLING_AUTH_URL}?{urlencode(auth_params)}"
    
    logger.info("oauth_authorize_redirect state=%s", state)
    
    return RedirectResponse(url=auth_url)


@router.post("/bling/connect", response_model=BlingAuthUrlResponse)
async def get_bling_auth_url(request: Request):
    """
    Generate Bling OAuth2 authorization URL (JSON response).
    
    **Response:**
    - `authorization_url`: URL to redirect user to for Bling authentication
    
    **Next Step:** User should visit this URL, authorize the app in Bling,
    then be redirected back to `/auth/bling/callback` with an authorization code.
    """
    
    state = str(uuid.uuid4())
    redirect_uri = _resolve_redirect_uri(request)
    _oauth_states[state] = {
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "redirect_uri": redirect_uri,
    }
    
    # Build auth URL with proper URL encoding
    auth_params = {
        "client_id": settings.BLING_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read write",
        "state": state,
    }
    auth_url = f"{settings.BLING_AUTH_URL}?{urlencode(auth_params)}"
    
    logger.info("oauth_authorize_url_generated state=%s", state)
    
    return BlingAuthUrlResponse(authorization_url=auth_url)



@router.get("/bling/callback")
async def bling_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Bling"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: Session = Depends(get_db),
):
    """
    Handle Bling OAuth2 callback.
    
    This endpoint is automatically called by Bling after user authorizes.
    It exchanges the authorization code for access/refresh tokens and stores them.
    
    **Params:**
    - `code`: Authorization code from Bling (valid for ~30 seconds)
    - `state`: CSRF protection token (must match request)
    
    **Returns:**
    - `message`: Confirmation message
    - `access_token`: Partial token (first 20 chars) for verification
    """
    
    request_id = str(uuid.uuid4())
    
    # Validate state
    state_data: Dict[str, Any] | None = _oauth_states.pop(state, None)
    if not state_data:
        logger.error("invalid_oauth_state state=%s", state)
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    expires_at = state_data.get("expires_at")
    if expires_at and datetime.utcnow() > expires_at:
        logger.error("expired_oauth_state state=%s", state)
        raise HTTPException(status_code=400, detail="Expired state parameter")

    redirect_uri = state_data.get("redirect_uri") or _resolve_redirect_uri(request)
    
    logger.info("oauth_callback_received code_length=%s", len(code) if code else 0)
    
    try:
        # Exchange code for tokens using Basic Auth
        # Bling requires client credentials in Basic Authentication header
        credentials = f"{settings.BLING_CLIENT_ID}:{settings.BLING_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        logger.info(
            "oauth_token_exchange_attempt redirect_uri=%s",
            redirect_uri,
        )

        max_attempts = 3
        token_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_attempts):
                token_response = await client.post(
                    settings.BLING_TOKEN_URL,
                    headers={
                        "Authorization": f"Basic {encoded_credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                )

                logger.info(
                    "oauth_token_response status_code=%s attempt=%s body=%s",
                    token_response.status_code,
                    attempt + 1,
                    token_response.text[:500],
                )

                if token_response.status_code != 429 or attempt >= (max_attempts - 1):
                    break

                retry_delay = _get_retry_delay_seconds(token_response, attempt)
                logger.warning(
                    "oauth_token_rate_limited status=429 attempt=%s retry_in=%ss",
                    attempt + 1,
                    round(retry_delay, 2),
                )
                await asyncio.sleep(retry_delay)

        if token_response is None:
            raise HTTPException(status_code=502, detail="No response from Bling token endpoint")

        token_response.raise_for_status()
        token_data = token_response.json()


        # Get or create default tenant
        tenant = BlingTokenRepository.get_or_create_default_tenant(db)

        # Store tokens (in production, encrypt them!)
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        logger.info(
            "oauth_saving_token expires_in=%s expires_at=%s now=%s",
            expires_in,
            expires_at.isoformat(),
            datetime.utcnow().isoformat(),
        )
        
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=tenant.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", ""),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            token_type=token_data.get("token_type", "Bearer"),
        )

        logger.info(
            f"oauth_token_saved - request_id={request_id}, tenant_id={str(tenant.id)}"
        )

        # Auto-trigger full sync if DB is empty (first connection)
        try:
            from app.repositories.order_snapshot_repo import OrderSnapshotRepository
            count = OrderSnapshotRepository.count_by_tenant(db, tenant.id)
            if count == 0:
                from app.api.orders import _run_sync_in_local_background
                logger.info("auto_sync_triggered tenant_id=%s reason=first_bling_connect", str(tenant.id))
                _run_sync_in_local_background("full")
        except Exception as exc:
            logger.warning("auto_sync_trigger_failed error=%s", str(exc))

        return TokenAuthResponse(
            message="Connected to Bling successfully",
            access_token=token_data["access_token"][:20] + "...",  # Partial for display
        )

    except httpx.HTTPError as e:
        bling_status = getattr(getattr(e, 'response', None), 'status_code', 'N/A')
        bling_body = ""
        if hasattr(e, 'response') and e.response is not None:
            try:
                bling_body = e.response.text[:500]
            except Exception:
                pass
        logger.error(
            "oauth_token_exchange_failed error=%s response_status=%s response_body=%s redirect_uri=%s",
            str(e),
            bling_status,
            bling_body,
            redirect_uri,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange code for tokens (Bling status={bling_status}): {bling_body}",
        )
    except Exception as e:
        logger.error("oauth_callback_error error=%s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )




@router.get("/bling/status")
async def check_bling_token_status(db: Session = Depends(get_db)):
    """
    Check if Bling token exists and is not expired.
    
    Returns:
        - valid: bool - Whether token exists and is not expired
        - message: str - Status message
    """
    from uuid import UUID
    
    TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
    
    try:
        token_repo = BlingTokenRepository()
        token = token_repo.get_by_tenant(db, TENANT_ID)
        
        if not token:
            return {
                "valid": False,
                "message": "No token found"
            }
        
        # Check if token is expired
        now = datetime.utcnow()
        
        logger.info(
            "checking_token_validity token_expires_at=%s now=%s is_expired=%s",
            token.expires_at.isoformat() if token.expires_at else "None",
            now.isoformat(),
            token.expires_at <= now if token.expires_at else "no_expiry",
        )
        
        if token.expires_at and token.expires_at <= now:
            return {
                "valid": False,
                "message": "Token expired"
            }
        
        # Token exists and is not expired
        return {
            "valid": True,
            "message": "Token is valid"
        }
            
    except Exception as e:
        logger.error(f"Error checking Bling token status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error checking token status"
        )
