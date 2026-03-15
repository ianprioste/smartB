"""Template Merge Engine

Merges Bling template payload with user overrides + computed SKU/name
for dry-run preview. It NEVER mutates the original template payload.
"""
from copy import deepcopy
from typing import Any, Dict, Optional

from app.models.schemas import PlanOverrides


class TemplateMerge:
    """Utility to merge template payload with overrides."""

    @staticmethod
    def merge(
        template_payload: Dict[str, Any],
        *,
        sku: str,
        name: str,
        overrides: PlanOverrides,
        price: float,
        model_name: str,
        print_name: str,
        brand_fallback: str = "Use Ruach",
    ) -> Dict[str, Any]:
        """
        Build computed payload preview.

        - Always overrides codigo and nome
        - Applies price
        - Applies descriptions if provided or derived
        - Applies category only when override is present
        - Keeps all other fields from the template intact
        """
        base = deepcopy(template_payload) if template_payload else {}

        # Always override SKU and name
        base["codigo"] = sku
        base["nome"] = name

        # Price (required per model)
        if price is not None:
            base["preco"] = price
            base["precoVenda"] = price  # defensively set both common fields

        # Determine brand for default descriptions
        brand = base.get("marca") or brand_fallback

        # Short description
        short_desc = overrides.short_description
        if not short_desc:
            short_desc = f"{print_name} - {model_name} | {brand}"
        base["descricaoCurta"] = short_desc

        # Complement description
        complement = base.get("descricaoComplementar")
        if overrides.complement_same_as_short:
            complement = short_desc
        elif overrides.complement_description:
            complement = overrides.complement_description
        # else: keep template's complement (already in base)
        base["descricaoComplementar"] = complement

        # Category override only when provided
        if overrides.category_override_id is not None:
            base["categoria_id"] = overrides.category_override_id

        # Fiscal classification overrides
        if overrides.ncm:
            base["ncm"] = overrides.ncm
        if overrides.cest:
            base["cest"] = overrides.cest

        return base
