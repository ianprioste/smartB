"""Pydantic schemas for API requests/responses."""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID


# ============ Auth Schemas ============

class BlingAuthUrlResponse(BaseModel):
    """Response with Bling authorization URL."""
    authorization_url: str = Field(description="URL to redirect user for Bling OAuth2")


class BlingCallbackRequest(BaseModel):
    """Bling OAuth2 callback request."""
    code: str = Field(description="Authorization code from Bling")
    state: Optional[str] = Field(None, description="Optional state parameter")


class BlingTokenResponse(BaseModel):
    """Bling token response."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"
    scope: Optional[str] = None


class TokenAuthResponse(BaseModel):
    """Successful authentication response."""
    message: str = "Connected to Bling successfully"
    access_token: Optional[str] = None


# ============ Job Schemas ============

class JobItemRequest(BaseModel):
    """Job item input."""
    payload: Dict[str, Any] = Field(default_factory=dict)


class JobItemResponse(BaseModel):
    """Job item response."""
    id: UUID
    job_id: UUID
    status: str
    payload: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobCreateRequest(BaseModel):
    """Create job request."""
    type: str = Field(description="Job type (e.g., 'sync_products')")
    input_payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Job response."""
    id: UUID
    type: str
    status: str
    input_payload: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = Field(None, alias="job_metadata")
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True
        populate_by_name = True


class JobDetailResponse(JobResponse):
    """Detailed job response with items."""
    items: List[JobItemResponse] = Field(default_factory=list)


# ============ Health Check ============

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
