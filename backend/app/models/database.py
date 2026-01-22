"""Data models for SQLAlchemy ORM."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Enum, JSON, Boolean, UniqueConstraint, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from app.infra.db import Base
import enum
from app.models.enums import TemplateKindEnum


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
