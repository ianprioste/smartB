"""Plan Builder for NEW_PRINT - Sprint 3.

This module generates complete execution plans for product creation
without writing anything to Bling.

Responsibilities:
- Validate templates and dependencies
- Generate SKUs using SkuEngine
- Check existing products in Bling (read-only)
- Produce preview with CREATE/UPDATE/NOOP/BLOCKED status
"""

from typing import List, Dict, Any, Optional
from app.domain.sku_engine import SkuEngine
from app.domain.template_merge import TemplateMerge
from app.models.schemas import (
    PlanNewRequest,
    PlanResponse,
    PlanItem,
    PlanSummary,
    PlanItemTemplate,
)
from app.models.enums import TemplateKindEnum, PlanItemActionEnum
from app.infra.logging import get_logger

logger = get_logger(__name__)


class PlanBuilderError(Exception):
    """Raised when plan building fails."""
    pass


class PlanBuilderNew:
    """
    Plan builder for NEW_PRINT operations.
    
    Generates a complete dry-run plan without executing anything.
    """

    def __init__(
        self,
        models_data: Dict[str, Dict],  # {code: {name, allowed_sizes, ...}}
        colors_data: Dict[str, str],  # {code: name}
        templates_data: Dict[str, Dict[str, int]],  # {model_code: {kind: bling_product_id}}
        bling_checker,  # Async function to fetch existing product detail by SKU
        bling_client=None,  # Optional Bling client to fetch template payloads
    ):
        """
        Initialize plan builder.
        
        Args:
            models_data: Model information {code: {name, allowed_sizes}}
            colors_data: Color information {code: name}
            templates_data: Template information {model_code: {kind: bling_product_id}}
            bling_checker: Async function(sku) -> Optional[Dict] to check Bling
        """
        self.models_data = models_data
        self.colors_data = colors_data
        self.templates_data = templates_data
        self.bling_checker = bling_checker
        self.bling_client = bling_client
        self.template_payloads: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.sku_engine = SkuEngine()

    async def build_plan(self, request: PlanNewRequest) -> PlanResponse:
        """
        Build complete plan from request.
        
        Args:
            request: Plan creation request
            
        Returns:
            Complete plan with preview
            
        Raises:
            PlanBuilderError: If validation fails
        """
        logger.info(f"Building plan for print {request.print.code}")

        # Validate input
        self._validate_input(request)

        # Load template payloads from Bling for merging
        await self._load_template_payloads()

        # Generate all plan items
        items = await self._generate_items(request)

        # Calculate summary
        summary = self._calculate_summary(request, items)

        # Check for blockers
        has_blockers = any(item.action == PlanItemActionEnum.BLOCKED for item in items)

        plan = PlanResponse(
            planVersion="1.0",
            type="NEW_PRINT",
            summary=summary,
            items=items,
            has_blockers=has_blockers,
        )

        logger.info(
            f"Plan generated: {summary.total_skus} SKUs, "
            f"CREATE={summary.create_count}, UPDATE={summary.update_count}, "
            f"NOOP={summary.noop_count}, BLOCKED={summary.blocked_count}"
        )

        return plan

    def _validate_input(self, request: PlanNewRequest) -> None:
        """
        Validate request input.
        
        Raises:
            PlanBuilderError: If validation fails
        """
        # Validate models exist
        for model_req in request.models:
            if model_req.code not in self.models_data:
                raise PlanBuilderError(
                    f"Model {model_req.code} not found in configuration"
                )

            if model_req.price is None or model_req.price <= 0:
                raise PlanBuilderError(
                    f"Model {model_req.code} must have price > 0"
                )

            # Validate sizes if provided
            if model_req.sizes:
                model_info = self.models_data[model_req.code]
                allowed_sizes = model_info.get("allowed_sizes", [])
                for size in model_req.sizes:
                    if size not in allowed_sizes:
                        raise PlanBuilderError(
                            f"Size {size} not allowed for model {model_req.code}. "
                            f"Allowed: {allowed_sizes}"
                        )

        # Validate colors exist
        for color_code in request.colors:
            if color_code not in self.colors_data:
                raise PlanBuilderError(
                    f"Color {color_code} not found in configuration"
                )

    async def _load_template_payloads(self) -> None:
        """Fetch template payloads from Bling for all templates in use."""
        if not self.bling_client:
            logger.warning("No bling_client provided; template payloads unavailable")
            return

        for model_code, kinds in self.templates_data.items():
            if model_code not in self.template_payloads:
                self.template_payloads[model_code] = {}

            for kind, bling_product_id in kinds.items():
                try:
                    payload = await self.bling_client.get_product(bling_product_id)
                    self.template_payloads[model_code][kind] = payload.get("data") if payload else None
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch template payload for {model_code}/{kind}: {e}"
                    )
                    self.template_payloads[model_code][kind] = None

    def _get_template_payload(
        self, model_code: str, template_kind: TemplateKindEnum
    ) -> Optional[Dict[str, Any]]:
        """Return cached template payload if available."""
        return self.template_payloads.get(model_code, {}).get(template_kind.value)

    async def _generate_items(self, request: PlanNewRequest) -> List[PlanItem]:
        """
        Generate all plan items.
        
        Args:
            request: Plan creation request
            
        Returns:
            List of plan items
        """
        items = []
        print_code = request.print.code
        print_name = request.print.name
        overrides = request.overrides
        model_codes = request.models

        # First pass: create PARENT_PRINTED for each model
        for model_req in model_codes:
            model_code = model_req.code
            model_info = self.models_data[model_code]
            model_name = model_info.get("name", model_code)
            model_price = model_req.price

            # Create parent SKU (once per model)
            parent_sku = self.sku_engine.parent_printed(model_code, print_code)
            parent_name = f"{model_name} {print_name}"
            parent_item = await self._create_plan_item(
                sku=parent_sku,
                entity="PARENT_PRINTED",
                model_code=model_code,
                template_kind=TemplateKindEnum.PARENT_PRINTED,
                dependencies=[],
                overrides=overrides,
                price=model_price,
                name=parent_name,
                model_name=model_name,
                print_name=print_name,
            )
            items.append(parent_item)

        # Second pass: create VARIATION_PRINTED for each color/size combination
        for model_req in model_codes:
            model_code = model_req.code
            model_info = self.models_data[model_code]
            model_name = model_info.get("name", model_code)
            model_price = model_req.price

            # Determine sizes
            if model_req.sizes:
                sizes = model_req.sizes
            else:
                sizes = model_info.get("allowed_sizes", [])

            # Parent for this model
            parent_sku = self.sku_engine.parent_printed(model_code, print_code)

            for color_code in request.colors:
                color_name = self.colors_data.get(color_code, color_code)
                for size in sizes:
                    # BASE_PLAIN already exists, just reference it as dependency
                    base_sku = self.sku_engine.base_plain(model_code, color_code, size)

                    # Create VARIATION_PRINTED item
                    variation_sku = self.sku_engine.variation_printed(
                        model_code, print_code, color_code, size
                    )
                    variation_name = f"{model_name} {print_name} {color_name} {size}"
                    variation_item = await self._create_plan_item(
                        sku=variation_sku,
                        entity="VARIATION_PRINTED",
                        model_code=model_code,
                        template_kind=TemplateKindEnum.PARENT_PRINTED,
                        dependencies=[parent_sku, base_sku],
                        overrides=overrides,
                        price=model_price,
                        name=variation_name,
                        model_name=model_name,
                        print_name=print_name,
                        color_name=color_name,
                        size=size,
                    )
                    items.append(variation_item)

        return items

    async def _create_plan_item(
        self,
        sku: str,
        entity: str,
        model_code: str,
        template_kind: TemplateKindEnum,
        dependencies: List[str],
        overrides: Any,
        price: float,
        name: str,
        model_name: str,
        print_name: str,
        color_name: Optional[str] = None,
        size: Optional[str] = None,
    ) -> PlanItem:
        """
        Create a single plan item with validation.
        
        Args:
            sku: Generated SKU
            entity: Entity type
            model_code: Model code
            template_kind: Template kind required
            dependencies: List of dependent SKUs
            
        Returns:
            Plan item with status
        """
        # Check if template exists
        template_missing = await self._check_template_missing(model_code, template_kind)
        template_payload = self._get_template_payload(model_code, template_kind)

        template_ref = {
            "model_code": model_code,
            "template_kind": template_kind.value,
            "bling_product_id": self.templates_data.get(model_code, {}).get(template_kind.value),
            "bling_product_sku": template_payload.get("codigo") if template_payload else None,
        }

        if template_missing or template_payload is None:
            reason = "MISSING_TEMPLATE" if template_missing else "MISSING_TEMPLATE_PAYLOAD"
            message = (
                f"Model {model_code} does not have template {template_kind.value} configured"
                if template_missing
                else f"Template payload unavailable for {model_code}/{template_kind.value}"
            )
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                dependencies=dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value),
                status=PlanItemActionEnum.BLOCKED,
                reason=reason,
                message=message,
                template_ref=template_ref,
            )

        # Compute payload preview
        computed_payload = TemplateMerge.merge(
            template_payload,
            sku=sku,
            name=name,
            overrides=overrides,
            price=price,
            model_name=model_name,
            print_name=print_name,
        )

        overrides_used = {
            "price": price,
            "short_description": computed_payload.get("descricaoCurta"),
            "complement_description": computed_payload.get("descricaoComplementar"),
            "category_override_id": overrides.category_override_id,
            "complement_same_as_short": overrides.complement_same_as_short,
        }

        # Check if SKU exists in Bling
        existing_product = await self._check_bling_product(sku)

        if existing_product is None:
            # SKU doesn't exist - CREATE
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.CREATE,
                dependencies=dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value),
                status=PlanItemActionEnum.CREATE,
                template_ref=template_ref,
                overrides_used=overrides_used,
                computed_payload_preview=computed_payload,
            )

        # SKU exists - check if needs update
        needs_update = self._check_needs_update(
            existing_product,
            computed_payload,
            category_override_active=overrides.category_override_id is not None,
        )

        if needs_update:
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.UPDATE,
                dependencies=dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value),
                status=PlanItemActionEnum.UPDATE,
                existing_product=existing_product,
                message="Product exists but needs update",
                template_ref=template_ref,
                overrides_used=overrides_used,
                computed_payload_preview=computed_payload,
            )

        # SKU exists and is correct - NOOP
        return PlanItem(
            sku=sku,
            entity=entity,
            action=PlanItemActionEnum.NOOP,
            dependencies=dependencies,
            template=PlanItemTemplate(model=model_code, kind=template_kind.value),
            status=PlanItemActionEnum.NOOP,
            existing_product=existing_product,
            message="Product already exists and is correct",
            template_ref=template_ref,
            overrides_used=overrides_used,
            computed_payload_preview=computed_payload,
        )

    async def _check_template_missing(
        self, model_code: str, template_kind: TemplateKindEnum
    ) -> bool:
        """
        Check if template is missing for model.
        
        Args:
            model_code: Model code
            template_kind: Template kind
            
        Returns:
            True if template is missing
        """
        if model_code not in self.templates_data:
            return True

        model_templates = self.templates_data[model_code]
        return template_kind.value not in model_templates

    async def _check_bling_product(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Check if product exists in Bling.
        
        Args:
            sku: SKU to check
            
        Returns:
            Product data if exists, None otherwise
        """
        if self.bling_checker is None:
            return None

        try:
            return await self.bling_checker(sku)
        except Exception as e:
            logger.warning(f"Error checking Bling product {sku}: {e}")
            return None

    def _check_needs_update(
        self,
        existing_product: Dict[str, Any],
        computed_payload: Dict[str, Any],
        *,
        category_override_active: bool,
    ) -> bool:
        """Compare existing product with computed payload to decide UPDATE/NOOP."""
        if not existing_product:
            return True

        # Fields we expect to match computed payload
        fields_to_compare = [
            "nome",
            "preco",
            "precoVenda",
            "descricaoCurta",
            "descricaoComplementar",
        ]

        for field in fields_to_compare:
            expected = computed_payload.get(field)
            if expected is None:
                continue
            if existing_product.get(field) != expected:
                return True

        if category_override_active:
            if existing_product.get("categoria_id") != computed_payload.get("categoria_id"):
                return True

        return False

    def _calculate_summary(
        self, request: PlanNewRequest, items: List[PlanItem]
    ) -> PlanSummary:
        """
        Calculate plan summary statistics.
        
        Args:
            request: Original request
            items: Generated plan items
            
        Returns:
            Summary statistics
        """
        create_count = sum(1 for item in items if item.action == PlanItemActionEnum.CREATE)
        update_count = sum(1 for item in items if item.action == PlanItemActionEnum.UPDATE)
        noop_count = sum(1 for item in items if item.action == PlanItemActionEnum.NOOP)
        blocked_count = sum(1 for item in items if item.action == PlanItemActionEnum.BLOCKED)

        return PlanSummary(
            models=len(request.models),
            colors=len(request.colors),
            total_skus=len(items),
            create_count=create_count,
            update_count=update_count,
            noop_count=noop_count,
            blocked_count=blocked_count,
        )
