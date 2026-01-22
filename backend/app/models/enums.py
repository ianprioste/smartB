"""Enumerations for Sprint 2 governance."""
import enum


class TemplateKindEnum(str, enum.Enum):
    """Model template kind enumeration."""
    BASE_PLAIN = "BASE_PLAIN"  # Template de produto liso do modelo
    STAMP = "STAMP"  # Template de estampa STM
    PARENT_PRINTED = "PARENT_PRINTED"  # Template do pai estampado
    VARIATION_PRINTED = "VARIATION_PRINTED"  # Template de variação estampada
