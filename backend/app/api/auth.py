"""Authentication endpoints for Bling OAuth2."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import httpx
import uuid
from urllib.parse import urlencode
import base64

from app.infra.db import get_db
from app.infra.logging import get_logger
from app.models.schemas import BlingAuthUrlResponse, BlingCallbackRequest, TokenAuthResponse
from app.repositories.bling_token_repo import BlingTokenRepository
from app.settings import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Store state for CSRF protection (in production, use secure session storage)
_oauth_states = {}


@router.get("/bling/connect")
async def bling_connect_redirect():
    """
    Redirect directly to Bling OAuth2 authorization page.
    
    This is the easiest way to re-authenticate:
    Just visit this URL in your browser and you'll be redirected to Bling.
    """
    
    state = str(uuid.uuid4())
    _oauth_states[state] = datetime.utcnow() + timedelta(minutes=10)
    
    # Build auth URL with proper URL encoding
    auth_params = {
        "client_id": settings.BLING_CLIENT_ID,
        "redirect_uri": settings.BLING_REDIRECT_URI,
        "response_type": "code",
        "scope": "read write",
        "state": state,
    }
    auth_url = f"{settings.BLING_AUTH_URL}?{urlencode(auth_params)}"
    
    logger.info(
        "oauth_authorize_redirect",
        state=state,
    )
    
    return RedirectResponse(url=auth_url)


@router.post("/bling/connect", response_model=BlingAuthUrlResponse)
async def get_bling_auth_url():
    """
    Generate Bling OAuth2 authorization URL (JSON response).
    
    **Response:**
    - `authorization_url`: URL to redirect user to for Bling authentication
    
    **Next Step:** User should visit this URL, authorize the app in Bling,
    then be redirected back to `/auth/bling/callback` with an authorization code.
    """
    
    state = str(uuid.uuid4())
    _oauth_states[state] = datetime.utcnow() + timedelta(minutes=10)
    
    # Build auth URL with proper URL encoding
    auth_params = {
        "client_id": settings.BLING_CLIENT_ID,
        "redirect_uri": settings.BLING_REDIRECT_URI,
        "response_type": "code",
        "scope": "read write",
        "state": state,
    }
    auth_url = f"{settings.BLING_AUTH_URL}?{urlencode(auth_params)}"
    
    logger.info(
        "oauth_authorize_url_generated",
        state=state,
    )
    
    return BlingAuthUrlResponse(authorization_url=auth_url)



@router.get("/bling/callback")
async def bling_callback(
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
    if state not in _oauth_states:
        logger.error(
            "invalid_oauth_state",
            state=state,
        )
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Clean up old states
    _oauth_states.pop(state, None)
    
    logger.info(
        "oauth_callback_received",
        code_length=len(code) if code else 0,
    )
    
    try:
        # Exchange code for tokens using Basic Auth
        # Bling requires client credentials in Basic Authentication header
        credentials = f"{settings.BLING_CLIENT_ID}:{settings.BLING_CLIENT_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        token_response = httpx.post(
            settings.BLING_TOKEN_URL,
            headers={
                "Authorization": f"Basic {encoded_credentials}",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.BLING_REDIRECT_URI,
            },
            timeout=30.0,
        )
        
        # Log response for debugging
        logger.info(
            "oauth_token_request_succeeded",
            status_code=token_response.status_code,
        )
        
        token_response.raise_for_status()
        token_data = token_response.json()


        # Get or create default tenant
        tenant = BlingTokenRepository.get_or_create_default_tenant(db)

        # Store tokens (in production, encrypt them!)
        expires_at = datetime.utcnow() + timedelta(
            seconds=token_data.get("expires_in", 3600)
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
            "oauth_token_saved",
            request_id=request_id,
            tenant_id=str(tenant.id),
        )
        return TokenAuthResponse(
            message="Connected to Bling successfully",
            access_token=token_data["access_token"][:20] + "...",  # Partial for display
        )

    except httpx.HTTPError as e:
        logger.error(
            "oauth_token_exchange_failed",
            error=str(e),
            response_status=getattr(e.response, 'status_code', 'N/A') if hasattr(e, 'response') else 'N/A',
        )
        raise HTTPException(
            status_code=400,
            detail="Failed to exchange code for tokens",
        )
    except Exception as e:
        logger.error(
            "oauth_callback_error",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )

