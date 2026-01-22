"""Pydantic schemas for API requests/responses."""
from pydantic import BaseModel, Field, field_validator
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


# ============ Sprint 2: Governance Schemas ============

# Models
class ModelCreateRequest(BaseModel):
    """Create model request."""
    code: str = Field(min_length=1, max_length=50, description="Model code (e.g., CAM)")
    name: str = Field(min_length=1, max_length=255, description="Model name (e.g., Camiseta)")
    allowed_sizes: List[str] = Field(min_items=1, description="Allowed sizes (e.g., ['P', 'M', 'G'])")
    size_order: Optional[List[str]] = Field(None, description="Optional size order (must be subset of allowed_sizes)")

    @field_validator("allowed_sizes")
    @classmethod
    def validate_allowed_sizes(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("allowed_sizes must not have duplicates")
        return v

    @field_validator("size_order")
    @classmethod
    def validate_size_order(cls, v, info):
        if v is None:
            return v
        allowed = info.data.get("allowed_sizes", [])
        if not all(size in allowed for size in v):
            raise ValueError("size_order must be a subset of allowed_sizes")
        return v


class ModelUpdateRequest(BaseModel):
    """Update model request."""
    name: Optional[str] = Field(None, max_length=255)
    allowed_sizes: Optional[List[str]] = Field(None, min_items=1)
    size_order: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("allowed_sizes")
    @classmethod
    def validate_allowed_sizes(cls, v):
        if v is not None and len(v) != len(set(v)):
            raise ValueError("allowed_sizes must not have duplicates")
        return v

    @field_validator("size_order")
    @classmethod
    def validate_size_order(cls, v, info):
        if v is None:
            return v
        allowed = info.data.get("allowed_sizes", [])
        if allowed and not all(size in allowed for size in v):
            raise ValueError("size_order must be a subset of allowed_sizes")
        return v


class ModelResponse(BaseModel):
    """Model response."""
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    allowed_sizes: List[str]
    size_order: Optional[List[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Colors
class ColorCreateRequest(BaseModel):
    """Create color request."""
    code: str = Field(min_length=1, max_length=50, description="Color code (e.g., BR)")
    name: str = Field(min_length=1, max_length=255, description="Color name (e.g., Branca)")


class ColorUpdateRequest(BaseModel):
    """Update color request."""
    name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class ColorResponse(BaseModel):
    """Color response."""
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Model Templates
class ModelTemplateCreateRequest(BaseModel):
    """Create model template request."""
    model_code: str = Field(min_length=1, max_length=50, description="Model code")
    template_kind: str = Field(description="Template kind (BASE_PLAIN, STAMP, PARENT_PRINTED, VARIATION_PRINTED)")
    bling_product_id: int = Field(description="Bling product ID")


class ModelTemplateResponse(BaseModel):
    """Model template response."""
    id: UUID
    tenant_id: UUID
    model_code: str
    template_kind: str
    bling_product_id: int
    bling_product_sku: str
    bling_product_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Bling Product Search
class BlingProductSearchItem(BaseModel):
    """Search result item for Bling product."""
    id: int
    codigo: str  # SKU
    nome: str
    formato: Optional[str] = None
    situacao: Optional[str] = None


class BlingProductSearchResponse(BaseModel):
    """Search response for Bling products."""
    total: int
    page: int
    limit: int
    items: List[BlingProductSearchItem]


class BlingProductDetailResponse(BaseModel):
    """Detailed Bling product response."""
    id: int
    codigo: str
    nome: str
    formato: Optional[str]
    situacao: Optional[str]
    descricao: Optional[str]
    preco: Optional[float]
    categoria_id: Optional[int]
    
    class Config:
        from_attributes = True


# Error Response
class ErrorResponse(BaseModel):
    """Standard error response."""
    code: str = Field(description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)")
    message: str = Field(description="User-friendly message")
    details: Optional[str] = Field(None, description="Technical details (safe to display)")

