"""
Centralized constants and enums for smartBling application.

This module provides a single source of truth for all magic strings, codes, and constants
used throughout the application. Consolidates repeated strings into named constants.
"""

from enum import Enum
from typing import Dict, List


# ====================================
# Plan & Execution Actions
# ====================================

class PlanActions(str, Enum):
    """Actions taken on plan items during execution."""
    
    CREATE = "CREATE"
    """Item does not exist - will be created."""
    
    UPDATE = "UPDATE"
    """Item exists and will be updated with new data."""
    
    NOOP = "NOOP"
    """No operation - item exists and matches expectations."""
    
    BLOCKED = "BLOCKED"
    """Blocked - dependencies not met or item is invalid."""


# ====================================
# Product & Entity Types
# ====================================

class EntityTypes(str, Enum):
    """Types of product entities in the system."""
    
    BASE_PLAIN = "BASE_PLAIN"
    """Base product without variations (format S)."""
    
    BASE_PARENT = "BASE_PARENT"
    """Base product with variations (format V)."""
    
    BASE_VARIATION = "BASE_VARIATION"
    """Variation of a base product (formato S inside V)."""
    
    PARENT_PRINTED = "PARENT_PRINTED"
    """Printed parent product (format V with format E variations)."""
    
    VARIATION_PRINTED = "VARIATION_PRINTED"
    """Printed variation product (format E with composition)."""


class ProductFormatos(str, Enum):
    """Bling product format types."""
    
    SIMPLE = "S"
    """Simple product without variations."""
    
    PARENT = "V"
    """Parent product with variations."""
    
    VARIATION = "E"
    """Variation of a parent product (with composition)."""


# ====================================
# HTTP & API
# ====================================

class HTTPStatus(int, Enum):
    """HTTP status codes used in API responses."""
    
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503


class ErrorCodes(str, Enum):
    """Application-specific error codes."""
    
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    BLING_API_ERROR = "BLING_API_ERROR"
    BLING_TOKEN_EXPIRED = "BLING_TOKEN_EXPIRED"
    BLING_RATE_LIMIT = "BLING_RATE_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ====================================
# Job & Task Status
# ====================================

class JobStatus(str, Enum):
    """Status of background jobs."""
    
    PENDING = "PENDING"
    """Job scheduled but not yet started."""
    
    RUNNING = "RUNNING"
    """Job is currently executing."""
    
    COMPLETED = "COMPLETED"
    """Job completed successfully."""
    
    FAILED = "FAILED"
    """Job failed with error."""
    
    CANCELLED = "CANCELLED"
    """Job was cancelled by user."""


# ====================================
# Logging & Environment
# ====================================

class LogLevels(str, Enum):
    """Application log levels."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environments(str, Enum):
    """Deployment environments."""
    
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# ====================================
# Configuration & Limits
# ====================================

class Limits:
    """Application limits and thresholds."""
    
    # Request limits
    MAX_MODELS_PER_WIZARD = 500
    MAX_COLORS_PER_WIZARD = 500
    MAX_TEMPLATES_PER_SEARCH = 1000
    
    # Bling API limits
    BLING_BATCH_SIZE = 100
    BLING_RATE_LIMIT_PER_MIN = 300
    BLING_REQUEST_TIMEOUT_SECS = 30
    BLING_RETRY_MAX_ATTEMPTS = 5
    BLING_RETRY_INITIAL_DELAY_SECS = 2
    
    # Cache limits
    CACHE_TOKEN_TTL_SECS = 1800  # 30 minutes
    CACHE_SKU_TTL_SECS = 300     # 5 minutes
    
    # Size limits
    MAX_BODY_SIZE_MB = 10
    MAX_FILENAME_LENGTH = 255


class SizeCodes:
    """Standard size codes used in variations."""
    
    CODES = ["XG", "GG", "G", "M", "P", "16", "14", "12", "10", "8", "6", "4", "2"]
    
    @staticmethod
    def is_valid(code: str) -> bool:
        """Check if code is a valid size code."""
        return code in SizeCodes.CODES


# ====================================
# Messages & Text
# ====================================

class Messages:
    """User-facing messages."""
    
    # Success messages
    WIZARD_COMPLETED = "Plano criado com sucesso!"
    MODELS_SAVED = "Modelos salvos com sucesso!"
    COLORS_SAVED = "Cores salvas com sucesso!"
    PLAN_EXECUTED = "Plano executado com sucesso!"
    
    # Error messages
    INVALID_INPUT = "Entrada inválida. Verifique e tente novamente."
    BLING_CONNECTION_ERROR = "Erro ao conectar com Bling. Verifique suas credenciais."
    BLING_TOKEN_EXPIRED_MSG = "Token Bling expirou. Por favor, faça login novamente."
    SERVER_ERROR = "Erro no servidor. Tente novamente mais tarde."
    
    # Info messages
    PROCESSING = "Processando..."
    LOADING = "Carregando..."


# ====================================
# Database & Schema
# ====================================

class DBDefaults:
    """Database default values."""
    
    # Field widths
    SKU_MAX_LENGTH = 100
    NAME_MAX_LENGTH = 255
    DESCRIPTION_MAX_LENGTH = 1000
    
    # Timestamps
    TIMEZONE = "UTC"


class TableNames:
    """Database table names (for reference)."""
    
    USERS = "users"
    BLING_TOKENS = "bling_tokens"
    MODELS = "models"
    COLORS = "colors"
    TEMPLATES = "templates"
    JOBS = "jobs"
    AUDIT_LOG = "audit_log"


# ====================================
# Feature Flags
# ====================================

class Features:
    """Feature flags for gradual rollout."""
    
    # Enable/disable features
    ENABLE_WIZARD = True
    ENABLE_ADMIN_PANEL = True
    ENABLE_BULK_OPERATIONS = True
    ENABLE_AUDIT_LOG = True
    
    # Beta features
    BETA_ADVANCED_FILTERS = False
    BETA_BATCH_SKU_IMPORT = False
    BETA_WEBHOOKS = False


# ====================================
# API Endpoints
# ====================================

class APIEndpoints:
    """API endpoint paths (for documentation)."""
    
    # Auth
    AUTH_LOGIN = "/auth/login"
    AUTH_CALLBACK = "/auth/callback"
    AUTH_LOGOUT = "/auth/logout"
    
    # Admin
    ADMIN_MODELS = "/admin/models"
    ADMIN_COLORS = "/admin/colors"
    ADMIN_TEMPLATES = "/admin/templates"
    
    # Plans
    PLANS_CREATE = "/plans"
    PLANS_LIST = "/plans"
    PLANS_EXECUTE = "/plans/execute"
    PLANS_SEED_BASES = "/plans/seed-bases"
    
    # Config
    CONFIG_BLING = "/config/bling"
    CONFIG_STATUS = "/config/status"


# ====================================
# Dictionaries & Mappings
# ====================================

# Action to description mapping
ACTION_DESCRIPTIONS: Dict[str, str] = {
    PlanActions.CREATE: "Será criado",
    PlanActions.UPDATE: "Será atualizado",
    PlanActions.NOOP: "Sem alterações",
    PlanActions.BLOCKED: "Bloqueado",
}

# Entity type to description mapping
ENTITY_DESCRIPTIONS: Dict[str, str] = {
    EntityTypes.BASE_PLAIN: "Base simples",
    EntityTypes.BASE_PARENT: "Base com variações",
    EntityTypes.BASE_VARIATION: "Variação de base",
    EntityTypes.PARENT_PRINTED: "Produto impresso",
    EntityTypes.VARIATION_PRINTED: "Variação impressa",
}

# Error code to message mapping
ERROR_MESSAGES: Dict[str, str] = {
    ErrorCodes.INVALID_REQUEST: "Requisição inválida",
    ErrorCodes.UNAUTHORIZED: "Não autorizado",
    ErrorCodes.FORBIDDEN: "Acesso negado",
    ErrorCodes.NOT_FOUND: "Recurso não encontrado",
    ErrorCodes.CONFLICT: "Conflito de dados",
    ErrorCodes.BLING_API_ERROR: "Erro na API Bling",
    ErrorCodes.BLING_TOKEN_EXPIRED: Messages.BLING_TOKEN_EXPIRED_MSG,
    ErrorCodes.BLING_RATE_LIMIT: "Rate limit atingido. Tente novamente em alguns minutos.",
    ErrorCodes.INTERNAL_ERROR: Messages.SERVER_ERROR,
}

# Status to CSS class mapping (for frontend)
STATUS_CSS_CLASSES: Dict[str, str] = {
    "success": "text-green-600 bg-green-50",
    "error": "text-red-600 bg-red-50",
    "warning": "text-yellow-600 bg-yellow-50",
    "info": "text-blue-600 bg-blue-50",
}
