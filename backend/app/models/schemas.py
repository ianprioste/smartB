"""Pydantic schemas for API requests/responses."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict, List
from datetime import datetime, date
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
    git_commit: str
    build_id: str
    build_timestamp: str


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
    bling_product_sku: Optional[str] = Field(None, description="Optional SKU from search result to avoid extra fetch")
    bling_product_name: Optional[str] = Field(None, description="Optional name from search result to avoid extra fetch")
    
    model_config = {"protected_namespaces": ()}


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

    model_config = {"protected_namespaces": (), "from_attributes": True}


# Bling Product Search
class BlingProductSearchItem(BaseModel):
    """Search result item for Bling product."""
    id: int
    codigo: str  # SKU
    nome: str
    formato: Optional[str] = None
    situacao: Optional[str] = None
    tipo_estoque: Optional[str] = None
    pai: Optional[int] = None  # Parent product ID if this is a variation
    quantidade_estoque: Optional[float] = None


class BlingProductSearchResponse(BaseModel):
    """Search response for Bling products."""
    total: int
    page: int
    limit: int
    items: List[BlingProductSearchItem]
    total_items: Optional[int] = None


class BlingProductDetailResponse(BaseModel):
    """Detailed Bling product response."""
    id: int
    codigo: str
    nome: str
    formato: Optional[str]
    situacao: Optional[str]
    descricao: Optional[str]
    descricao_curta: Optional[str] = None
    descricao_complementar: Optional[str] = None
    preco: Optional[float]
    categoria_id: Optional[int]
    
    class Config:
        from_attributes = True


# ============ Orders Response Schemas ============

class OrderItemResponse(BaseModel):
    """Item/product in an order."""
    sku: Optional[str] = None
    product_name: str = "Produto"
    quantity: float = 0.0
    unit_price: float = 0.0
    total: float = 0.0
    paid_unit_price: float = 0.0
    paid_total: float = 0.0


class OrderDetailsResponse(BaseModel):
    """Complete order with items."""
    id: Optional[int]
    numero: Optional[int]
    numeroLoja: Optional[str]
    data: Optional[str]
    cliente: str
    total: float
    situacao: str
    situacaoId: Optional[int]
    itens: List[OrderItemResponse] = Field(default_factory=list)


# Error Response
class ErrorResponse(BaseModel):
    """Standard error response."""
    code: str = Field(description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)")
    message: str = Field(description="User-friendly message")
    details: Optional[str] = Field(None, description="Technical details (safe to display)")


# ============ Sprint 3: Plan Builder Schemas ============

# Plan Creation Request
class PlanModelRequest(BaseModel):
    """Model and sizes for plan request."""
    code: str = Field(min_length=1, max_length=50, description="Model code (e.g., CAM)")
    sizes: Optional[List[str]] = Field(None, description="Sizes for this model (if not provided, use allowed_sizes)")
    price: float = Field(gt=0, description="Required price for this model")

    class Config:
        protected_namespaces = ()


class PlanPrintInfo(BaseModel):
    """Print information for plan."""
    code: str = Field(min_length=1, max_length=50, description="Print code (e.g., STPV)")
    name: str = Field(min_length=1, max_length=255, description="Print name")


class PlanOverrides(BaseModel):
    """User-provided overrides for variable fields."""
    short_description: Optional[str] = Field(None, description="Override for descricaoCurta")
    complement_description: Optional[str] = Field(None, description="Override for descricaoComplementar")
    complement_same_as_short: bool = Field(default=True, description="If true, complement = short description")
    category_override_id: Optional[int] = Field(None, description="Override for category id; null keeps template category")
    ncm: Optional[str] = Field(None, description="Override for NCM")
    cest: Optional[str] = Field(None, description="Override for CEST")

    class Config:
        protected_namespaces = ()


class PlanOptions(BaseModel):
    """Plan execution options and toggles."""
    auto_seed_base_plain: bool = Field(default=False, description="Auto-seed missing base plain (BASE_PARENT, BASE_VARIATION) templates")
    stock_type: str = Field(default="virtual", description="Stock type: 'virtual' (composition, tipoEstoque=V) or 'physical' (variation, utilizarDadosDoPai=true)")

    class Config:
        protected_namespaces = ()


class PlanNewRequest(BaseModel):
    """Create new print plan request."""
    print: PlanPrintInfo = Field(description="Print information")
    models: List[PlanModelRequest] = Field(min_items=1, description="Models to create")
    colors: List[str] = Field(min_items=1, description="Color codes to use")
    overrides: PlanOverrides = Field(default_factory=PlanOverrides, description="Optional overrides for variable fields")
    options: PlanOptions = Field(default_factory=PlanOptions, description="Plan execution options and toggles")
    edit_parent_id: Optional[int] = Field(None, description="Bling product ID being edited (track by ID instead of by SKU)")


class PlanPlainRequest(BaseModel):
    """Create plain product plan request."""
    parent_sku: str = Field(min_length=1, max_length=100, description="Parent SKU defined by user")
    parent_name: str = Field(min_length=1, max_length=255, description="Parent product name defined by user")
    model_code: str = Field(min_length=1, max_length=50, description="Model code to use templates/sizes")
    sizes: Optional[List[str]] = Field(None, description="Sizes for this model (if not provided, use allowed_sizes)")
    colors: List[str] = Field(min_items=1, description="Color codes to use")
    price: float = Field(gt=0, description="Required price for parent/children")
    overrides: PlanOverrides = Field(default_factory=PlanOverrides, description="Optional overrides for variable fields")
    options: PlanOptions = Field(default_factory=PlanOptions, description="Plan execution options and toggles")
    edit_parent_id: Optional[int] = Field(None, description="Bling product ID being edited (optional)")


# Plan Item
class PlanItemTemplate(BaseModel):
    """Template information for plan item."""
    model: str = Field(description="Model code")
    kind: str = Field(description="Template kind")
    fallback_used: bool = Field(default=False, description="Whether fallback template was used (VARIATION_PRINTED using BASE_PLAIN)")


class SeedSummary(BaseModel):
    """Seed summary for auto-seed feature."""
    base_parent_missing: List[str] = Field(default_factory=list, description="Missing BASE_PARENT SKUs")
    base_variation_missing: List[str] = Field(default_factory=list, description="Missing BASE_VARIATION SKUs")
    total_missing: int = Field(default=0, description="Total missing base SKUs")
    total_included: int = Field(default=0, description="Total included base SKUs in plan")


class PlanItem(BaseModel):
    """Individual plan item."""
    sku: str = Field(description="Generated SKU")
    entity: str = Field(description="Entity type (BASE_PLAIN, PARENT_PRINTED, VARIATION_PRINTED)")
    action: str = Field(description="Action to take (CREATE, UPDATE, NOOP, BLOCKED)")
    hard_dependencies: List[str] = Field(default_factory=list, description="Hard dependencies (blocking if missing)")
    soft_dependencies: List[str] = Field(default_factory=list, description="Soft dependencies (optional but recommended)")
    template: Optional[PlanItemTemplate] = Field(None, description="Template information")
    status: str = Field(description="Status of the item")
    reason: Optional[str] = Field(None, description="Reason for BLOCKED status")
    message: Optional[str] = Field(None, description="Detailed message")
    warnings: List[str] = Field(default_factory=list, description="Warning messages (e.g., missing soft dependencies)")
    diff_summary: List[str] = Field(default_factory=list, description="Summary of changes for UPDATE status (e.g., ['preco', 'nome'])")
    existing_product: Optional[Dict[str, Any]] = Field(None, description="Existing product info from Bling")
    template_ref: Optional[Dict[str, Any]] = Field(None, description="Reference to template used (model_code, kind, bling_product_id, bling_product_sku)")
    overrides_used: Optional[Dict[str, Any]] = Field(None, description="Overrides applied for this item")
    computed_payload_preview: Optional[Dict[str, Any]] = Field(None, description="Merged payload (template + overrides + SKU/Name)")
    autoseed_candidate: bool = Field(default=False, description="Whether this is an auto-seed candidate")
    included: bool = Field(default=True, description="Whether this item is included in the plan")
    force_update_id: Optional[int] = Field(None, description="Bling product ID to use directly for update (bypasses SKU lookup)")
    planned_deletions: List[str] = Field(default_factory=list, description="Variation SKUs expected to be removed on UPDATE sync")


class PlanSummary(BaseModel):
    """Plan summary statistics."""
    models: int = Field(description="Number of models")
    colors: int = Field(description="Number of colors")
    total_skus: int = Field(description="Total SKUs generated")
    create_count: int = Field(default=0, description="Number of CREATE actions")
    update_count: int = Field(default=0, description="Number of UPDATE actions")
    noop_count: int = Field(default=0, description="Number of NOOP actions")
    blocked_count: int = Field(default=0, description="Number of BLOCKED actions")


class PlanResponse(BaseModel):
    """Plan response.
    
    IMPORTANT - Executor Usage (Sprint 4):
    =====================================
    When executing this plan, the executor MUST:
    1. Only iterate items where action in {'CREATE', 'UPDATE'}
    2. Skip items where action == 'BLOCKED' (not executable)
    3. Skip items where action == 'NOOP' (already correct in Bling)
    4. Never execute items with reason='MISSING_TEMPLATE_PAYLOAD'
    
    The 'has_blockers' flag indicates whether user review is needed before execution.
    If has_blockers=true, user should review and fix issues (missing templates, etc.)
    """
    planVersion: str = Field(default="1.0", description="Plan version")
    type: str = Field(description="Plan type (NEW_PRINT)")
    summary: PlanSummary = Field(description="Summary statistics")
    items: List[PlanItem] = Field(description="Plan items")
    has_blockers: bool = Field(description="Whether plan has blocked items")
    seed_summary: SeedSummary = Field(default_factory=SeedSummary, description="Seed summary for auto-seed feature")
    options: PlanOptions = Field(default_factory=PlanOptions, description="Plan options used")


class PlanSaveRequest(BaseModel):
    """Save plan request."""
    plan: PlanResponse = Field(description="Plan to save")


class PlanSavedResponse(BaseModel):
    """Plan saved response."""
    id: UUID = Field(description="Plan ID")
    type: str = Field(description="Plan type")
    status: str = Field(description="Plan status")
    created_at: datetime = Field(description="Creation timestamp")

    class Config:
        from_attributes = True


# ============ Sales Events ============

class SalesEventProductInput(BaseModel):
    """Product selected for a sales event."""
    bling_product_id: Optional[int] = None
    sku: str = Field(min_length=1, max_length=255)
    product_name: Optional[str] = Field(None, max_length=500)


class SalesEventCreateRequest(BaseModel):
    """Create a sales event."""
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    products: List[SalesEventProductInput] = Field(min_items=1)

    @field_validator("end_date")
    @classmethod
    def validate_period(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be greater than or equal to start_date")
        return v


class SalesEventUpdateRequest(BaseModel):
    """Update a sales event."""
    name: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    products: List[SalesEventProductInput] = Field(min_items=1)

    @field_validator("end_date")
    @classmethod
    def validate_period(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be greater than or equal to start_date")
        return v


class SalesEventProductResponse(BaseModel):
    id: UUID
    bling_product_id: Optional[int]
    sku: str
    product_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SalesEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
    products: List[SalesEventProductResponse] = Field(default_factory=list)


class SalesEventListItemResponse(BaseModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    products_count: int
        is_active: bool = True
    created_at: datetime


class EventMatchedItemResponse(BaseModel):
    sku: str
    product_name: str
    quantity: float
    unit_price: float
    total: float
    paid_unit_price: float
    paid_total: float
    production_status: str = "Pendente"
    notes: Optional[str] = None


class EventOrderResponse(BaseModel):
    id: Optional[int] = None
    numero: Optional[int] = None
    numero_loja: Optional[str] = None
    data: Optional[str] = None
    cliente: str = "—"
    situacao: str = "—"
    total_order: float = 0.0
    total_matched: float = 0.0
    has_frete: bool = False
    production_summary: Optional[str] = None
    matched_items: List[EventMatchedItemResponse] = Field(default_factory=list)


class EventSalesSummaryResponse(BaseModel):
    orders_count: int = 0
    matched_items_count: int = 0
    total_matched: float = 0.0


class EventSalesResponse(BaseModel):
    event: SalesEventResponse
    summary: EventSalesSummaryResponse
    orders: List[EventOrderResponse] = Field(default_factory=list)


class ItemProductionNoteUpdateRequest(BaseModel):
    production_status: str
    notes: Optional[str] = None
    bling_order_id: Optional[int] = None


class ItemProductionNoteResponse(BaseModel):
    sku: str
    production_status: str
    notes: Optional[str] = None
    bling_order_id: Optional[int] = None


class OrderStatusUpdateRequest(BaseModel):
    situacao: str


