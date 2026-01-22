"""Enumerations for Sprint 2 governance and Sprint 3 plans."""
import enum


class TemplateKindEnum(str, enum.Enum):
    """Model template kind enumeration."""
    BASE_PLAIN = "BASE_PLAIN"  # Template de produto liso do modelo
    BASE_PARENT = "BASE_PARENT"  # Template de pai liso (para autoseed)
    BASE_VARIATION = "BASE_VARIATION"  # Template de variação lisa (para autoseed)
    PARENT_PRINTED = "PARENT_PRINTED"  # Template do pai estampado
    VARIATION_PRINTED = "VARIATION_PRINTED"  # Template de variação estampada


class PlanTypeEnum(str, enum.Enum):
    """Plan type enumeration."""
    NEW_PRINT = "NEW_PRINT"  # New print creation plan
    FIX = "FIX"  # Fix/correction plan (future sprint)


class PlanStatusEnum(str, enum.Enum):
    """Plan status enumeration."""
    DRAFT = "DRAFT"  # Plan generated but not executed
    EXECUTED = "EXECUTED"  # Plan executed successfully


class PlanItemActionEnum(str, enum.Enum):
    """Plan item action enumeration."""
    CREATE = "CREATE"  # SKU needs to be created
    UPDATE = "UPDATE"  # SKU exists but needs update
    NOOP = "NOOP"  # SKU exists and is correct
    BLOCKED = "BLOCKED"  # SKU cannot be processed (missing dependencies/templates)
