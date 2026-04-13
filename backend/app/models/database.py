"""Data models for SQLAlchemy ORM."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date, Integer, Text, ForeignKey, Enum, JSON, Boolean, UniqueConstraint, BigInteger, Float, TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.infra.db import Base
from app.settings import settings
import enum
from app.models.enums import TemplateKindEnum, PlanTypeEnum, PlanStatusEnum


# Cross-database UUID type: uses native PG UUID when on PostgreSQL, CHAR(32) otherwise.
class UUID(TypeDecorator):
    """Platform-independent UUID type."""
    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid=True):
        self.as_uuid = as_uuid
        super().__init__(length=32)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value) if not isinstance(value, uuid.UUID) else value
        if isinstance(value, uuid.UUID):
            return value.hex
        return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


class TenantModel(Base):
    """Tenant/Account model."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BlingTokenModel(Base):
    """Bling OAuth2 tokens storage."""
    __tablename__ = "bling_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    access_token = Column(Text, nullable=False)  # Encrypted in production
    refresh_token = Column(Text, nullable=False)  # Encrypted in production
    expires_at = Column(DateTime, nullable=False)
    token_type = Column(String(50), default="Bearer")
    scope = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobStatusEnum(str, enum.Enum):
    """Job status enumeration."""
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class JobItemStatusEnum(str, enum.Enum):
    """Job item status enumeration."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OK = "OK"
    ERROR = "ERROR"


class JobModel(Base):
    """Jobs table for tracking async operations."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    type = Column(String(100), nullable=False)  # e.g., "sync_products", "update_inventory"
    status = Column(Enum(JobStatusEnum), nullable=False, default=JobStatusEnum.DRAFT)
    input_payload = Column(JSON, nullable=True)
    job_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class JobItemModel(Base):
    """Individual items within a job."""
    __tablename__ = "job_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    status = Column(Enum(JobItemStatusEnum), nullable=False, default=JobItemStatusEnum.PENDING)
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class ModelModel(Base):
    """Product models/styles (e.g., CAM, BL, INF)."""
    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., CAM, BL
    name = Column(String(255), nullable=False)  # e.g., Camiseta, Babylook
    allowed_sizes = Column(JSON, nullable=False)  # Array of strings, no duplicates
    size_order = Column(JSON, nullable=True)  # Optional subset of allowed_sizes
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_models_tenant_code"),
    )


class ColorModel(Base):
    """Product colors (e.g., BR, PR, OW)."""
    __tablename__ = "colors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g., BR, PR
    name = Column(String(255), nullable=False)  # e.g., Branca, Preta
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_colors_tenant_code"),
    )


class ModelTemplateModel(Base):
    """Templates for product models (which Bling product to use as base)."""
    __tablename__ = "model_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    model_code = Column(String(50), nullable=False)  # FK logical to models.code
    template_kind = Column(Enum(TemplateKindEnum), nullable=False)
    bling_product_id = Column(BigInteger, nullable=False)  # Bling product ID
    bling_product_sku = Column(String(255), nullable=False)  # For audit trail
    bling_product_name = Column(String(500), nullable=True)  # For audit trail
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "model_code", "template_kind", name="uq_model_templates_tenant_model_kind"),
    )


class PlanModel(Base):
    """Plans for product creation/update operations."""
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    type = Column(Enum(PlanTypeEnum), nullable=False)  # NEW_PRINT, FIX
    status = Column(Enum(PlanStatusEnum), nullable=False, default=PlanStatusEnum.DRAFT)
    input_payload = Column(JSON, nullable=False)  # Original request that generated the plan
    plan_payload = Column(JSON, nullable=False)  # Complete plan with all items
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)  # When execution started


class SalesEventModel(Base):
    """Sales event definition (name, period, and tracked products)."""
    __tablename__ = "sales_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SalesEventProductModel(Base):
    """Products associated to a sales event."""
    __tablename__ = "sales_event_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("sales_events.id"), nullable=False)
    bling_product_id = Column(BigInteger, nullable=True)
    sku = Column(String(255), nullable=False)
    product_name = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", "sku", name="uq_sales_event_products_event_sku"),
    )


class ItemProductionNoteModel(Base):
    """User-managed production status and notes per item+order in an event. Independent from Bling sync."""
    __tablename__ = "item_production_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("sales_events.id"), nullable=False)
    sku = Column(String(255), nullable=False)
    bling_order_id = Column(BigInteger, nullable=True)
    production_status = Column(String(100), nullable=False, default="Pendente")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", "sku", "bling_order_id", name="uq_item_production_notes_tenant_event_sku_order"),
    )


class BlingOrderSnapshotModel(Base):
    """Persistent local snapshot of Bling orders and full details."""
    __tablename__ = "bling_order_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    bling_order_id = Column(BigInteger, nullable=False)

    numero = Column(BigInteger, nullable=True)
    numero_loja = Column(String(255), nullable=True)
    order_date = Column(DateTime, nullable=True)
    customer_name = Column(String(500), nullable=True)
    status_id = Column(Integer, nullable=True)
    status_name = Column(String(255), nullable=True)
    total_value = Column(Float, nullable=True)

    raw_order = Column(JSON, nullable=True)   # payload from /pedidos/vendas list
    raw_detail = Column(JSON, nullable=True)  # payload from /pedidos/vendas/{id}

    source_updated_at = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "bling_order_id", name="uq_bling_order_snapshot_tenant_order"),
    )


class OrderTagModel(Base):
    """Reusable order tags scoped to global orders or a specific sales event."""
    __tablename__ = "order_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    scope_key = Column(String(20), nullable=False)  # global | event
    event_id = Column(UUID(as_uuid=True), ForeignKey("sales_events.id"), nullable=True)
    name = Column(String(80), nullable=False)
    name_key = Column(String(80), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_key", "event_id", "name_key", name="uq_order_tags_tenant_scope_event_name"),
    )


class OrderTagAssignmentModel(Base):
    """One tag assignment per order within a given scope."""
    __tablename__ = "order_tag_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    scope_key = Column(String(20), nullable=False)  # global | event
    event_id = Column(UUID(as_uuid=True), ForeignKey("sales_events.id"), nullable=True)
    bling_order_id = Column(BigInteger, nullable=False)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("order_tags.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_key", "event_id", "bling_order_id", name="uq_order_tag_assignments_tenant_scope_event_order"),
    )


class OrderTagLinkModel(Base):
    """Many-to-many links between orders and reusable tags within a scope."""
    __tablename__ = "order_tag_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    scope_key = Column(String(20), nullable=False)  # global | event
    event_id = Column(UUID(as_uuid=True), ForeignKey("sales_events.id"), nullable=True)
    bling_order_id = Column(BigInteger, nullable=False)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("order_tags.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_key", "event_id", "bling_order_id", "tag_id", name="uq_order_tag_links_tenant_scope_event_order_tag"),
    )


class BlingOrdersSyncStateModel(Base):
    """Tracks last sync checkpoints for Bling orders import."""
    __tablename__ = "bling_orders_sync_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    last_full_sync_at = Column(DateTime, nullable=True)
    last_incremental_sync_at = Column(DateTime, nullable=True)
    last_successful_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_message = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_bling_orders_sync_state_tenant"),
    )


class SyncScopeVersionModel(Base):
    """Monotonic version token per tenant+scope for lightweight cross-device sync."""
    __tablename__ = "sync_scope_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    scope_key = Column(String(255), nullable=False)
    version = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_key", name="uq_sync_scope_versions_tenant_scope"),
    )


class AccessProfileModel(Base):
    """Access profile (role) used by allowed emails."""
    __tablename__ = "access_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    permissions = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_access_profiles_tenant_name"),
    )


class AccessUserModel(Base):
    """Allowed app user identified by e-mail."""
    __tablename__ = "access_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(320), nullable=False)
    password_hash = Column(String(255), nullable=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("access_profiles.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_access_users_tenant_email"),
    )


class AccessSessionModel(Base):
    """Authenticated app session stored server-side."""
    __tablename__ = "access_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("access_users.id"), nullable=False)
    token = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("token", name="uq_access_sessions_token"),
    )


class PasswordResetCodeModel(Base):
    """One-time password reset code for access users."""
    __tablename__ = "password_reset_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("access_users.id"), nullable=False)
    email = Column(String(320), nullable=False)
    code_hash = Column(String(255), nullable=False)
    attempts_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

