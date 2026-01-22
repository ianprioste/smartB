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
    SeedSummary,
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

        # First, detect and verify if any seeds were manually created in Bling
        # This needs to happen BEFORE generating items so that VARIATION_PRINTED
        # items don't get marked as BLOCKED due to missing dependencies
        verified_manual_seeds = []
        if not request.options.auto_seed_base_plain:
            # Try to detect and verify manually created seeds
            all_possible_seeds = await self._get_all_possible_seeds(request)
            verified_manual_seeds = await self._verify_manually_created_seeds(all_possible_seeds)
            
            # Pre-populate items with verified seeds so they're available during generation
            items = []
            for verified_seed in verified_manual_seeds:
                items.append(verified_seed)
        else:
            items = []

        # Generate all plan items (including VARIATION_PRINTED which will see verified seeds)
        generated_items = await self._generate_items(request)
        items.extend(generated_items)

        # Always detect missing base seeds (to populate seed_summary for UI toggle)
        detected_seeds = await self._detect_missing_base_seeds(request, items)
        
        # Initialize seed_summary with detected missing seeds
        seed_summary = SeedSummary()
        
        # If auto-seed disabled, only show remaining missing seeds (after manual verification)
        if not request.options.auto_seed_base_plain:
            verified_skus = {v.sku for v in verified_manual_seeds}
            remaining_missing = [s for s in detected_seeds if s.sku not in verified_skus]
            seed_summary.base_parent_missing = [
                item.sku for item in remaining_missing if item.entity == "BASE_PARENT"
            ]
            seed_summary.base_variation_missing = [
                item.sku for item in remaining_missing if item.entity == "BASE_VARIATION"
            ]
            # Auto-seed mode: show all detected missing seeds
            seed_summary.base_parent_missing = [
                item.sku for item in detected_seeds if item.entity == "BASE_PARENT"
            ]
            seed_summary.base_variation_missing = [
                item.sku for item in detected_seeds if item.entity == "BASE_VARIATION"
            ]
        
        seed_summary.total_missing = len(seed_summary.base_parent_missing) + len(seed_summary.base_variation_missing)
        
        # If auto-seed enabled, add items to plan and update seed_summary
        if request.options.auto_seed_base_plain:
            seed_items = await self._add_base_seed_items(request, items, detected_seeds)
            items.extend(seed_items)
            seed_summary.total_included = sum(1 for item in seed_items if item.included)

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
            seed_summary=seed_summary,
            options=request.options,
        )

        logger.info(
            f"Plan generated: {summary.total_skus} SKUs, "
            f"CREATE={summary.create_count}, UPDATE={summary.update_count}, "
            f"NOOP={summary.noop_count}, BLOCKED={summary.blocked_count}"
        )

        return plan

    async def _detect_missing_base_seeds(
        self, request: PlanNewRequest, items: List[PlanItem]
    ) -> List[PlanItem]:
        """
        Detect missing BASE_PARENT and BASE_VARIATION seeds for VARIATION_PRINTED items.
        Returns seed items that WOULD be needed, without including them=true yet.
        
        Args:
            request: Plan creation request
            items: Generated plan items
            
        Returns:
            List of detected seed items (as seeds, not for adding to plan yet)
        """
        detected_seeds = []
        existing_skus = {item.sku for item in items}
        created_seeds: Dict[str, PlanItem] = {}
        
        # Process VARIATION_PRINTED items to identify missing base seeds
        for item in items:
            if item.entity != "VARIATION_PRINTED":
                continue
            
            # Extract model, color, size from the variation item
            for model_req in request.models:
                model_code = model_req.code
                
                for color_code in request.colors:
                    # Determine sizes
                    if model_req.sizes:
                        sizes = model_req.sizes
                    else:
                        model_info = self.models_data.get(model_code, {})
                        sizes = model_info.get("allowed_sizes", [])
                    
                    for size in sizes:
                        # Generate expected variation SKU to match
                        expected_variation_sku = self.sku_engine.variation_printed(
                            model_code, request.print.code, color_code, size
                        )
                        
                        if item.sku != expected_variation_sku:
                            continue
                        
                        # Found matching variation - detect BASE_PARENT if missing
                        base_parent_sku = model_code.upper()
                        if base_parent_sku not in existing_skus and base_parent_sku not in created_seeds:
                            base_parent_seed = await self._create_seed_item(
                                sku=base_parent_sku,
                                entity="BASE_PARENT",
                                model_code=model_code,
                                request=request,
                                included=False,  # Detection only, not included yet
                            )
                            if base_parent_seed:
                                created_seeds[base_parent_sku] = base_parent_seed
                                existing_skus.add(base_parent_sku)
                        
                        # Detect BASE_VARIATION if missing
                        base_variation_sku = self.sku_engine.base_plain(model_code, color_code, size)
                        if base_variation_sku not in existing_skus and base_variation_sku not in created_seeds:
                            base_variation_seed = await self._create_seed_item(
                                sku=base_variation_sku,
                                entity="BASE_VARIATION",
                                model_code=model_code,
                                request=request,
                                included=False,  # Detection only, not included yet
                            )
                            if base_variation_seed:
                                created_seeds[base_variation_sku] = base_variation_seed
                                existing_skus.add(base_variation_sku)
        
        detected_seeds.extend(created_seeds.values())
        return detected_seeds

    async def _get_all_possible_seeds(
        self, request: PlanNewRequest
    ) -> List[PlanItem]:
        """
        Generate list of all possible seeds that COULD be created for this plan.
        This is used to check if user manually created them in Bling.
        
        Args:
            request: Plan creation request
            
        Returns:
            List of possible seed items (not yet verified in Bling)
        """
        possible_seeds = []
        created_seeds: Dict[str, PlanItem] = {}
        
        # For each model/color/size combination, generate possible BASE_PARENT and BASE_VARIATION seeds
        for model_req in request.models:
            model_code = model_req.code
            
            # Generate BASE_PARENT
            base_parent_sku = model_code.upper()
            if base_parent_sku not in created_seeds:
                base_parent_seed = await self._create_seed_item(
                    sku=base_parent_sku,
                    entity="BASE_PARENT",
                    model_code=model_code,
                    request=request,
                    included=False,
                )
                if base_parent_seed:
                    created_seeds[base_parent_sku] = base_parent_seed
            
            # Generate BASE_VARIATION for each color/size
            for color_code in request.colors:
                if model_req.sizes:
                    sizes = model_req.sizes
                else:
                    model_info = self.models_data.get(model_code, {})
                    sizes = model_info.get("allowed_sizes", [])
                
                for size in sizes:
                    base_variation_sku = self.sku_engine.base_plain(model_code, color_code, size)
                    if base_variation_sku not in created_seeds:
                        base_variation_seed = await self._create_seed_item(
                            sku=base_variation_sku,
                            entity="BASE_VARIATION",
                            model_code=model_code,
                            request=request,
                            included=False,
                        )
                        if base_variation_seed:
                            created_seeds[base_variation_sku] = base_variation_seed
        
        possible_seeds.extend(created_seeds.values())
        return possible_seeds

    async def _verify_manually_created_seeds(
        self, detected_seeds: List[PlanItem]
    ) -> List[PlanItem]:
        """
        Verify if manually created seeds exist in Bling.
        Checks each detected seed against Bling and creates UPDATE items for found seeds.
        
        Args:
            detected_seeds: Seeds that were detected as missing
            
        Returns:
            List of seed items found in Bling (as UPDATE items)
        """
        verified_seeds = []
        
        for seed in detected_seeds:
            try:
                # Check if seed exists in Bling
                existing = await self.bling_checker(seed.sku)
                
                if existing:
                    # Seed was created manually in Bling - add as UPDATE
                    verified_seed = PlanItem(
                        sku=seed.sku,
                        entity=seed.entity,
                        action=PlanItemActionEnum.UPDATE,
                        hard_dependencies=[],
                        soft_dependencies=[],
                        template=seed.template,
                        status=PlanItemActionEnum.UPDATE,
                        reason="MANUALLY_CREATED",
                        message=f"{seed.entity} foi criado manualmente no Bling",
                        overrides_used={},
                        autoseed_candidate=True,
                        included=True,
                    )
                    verified_seeds.append(verified_seed)
                    logger.info(f"Seed {seed.sku} found in Bling (manually created)")
            except Exception as e:
                # If check fails, just skip this seed
                logger.warning(f"Error verifying seed {seed.sku}: {str(e)}")
                continue
        
        return verified_seeds

    async def _add_base_seed_items(
        self, request: PlanNewRequest, items: List[PlanItem], detected_seeds: List[PlanItem]
    ) -> List[PlanItem]:
        """
        Add detected base seed items to the plan with included=true when auto_seed_base_plain is enabled.
        Also updates VARIATION_PRINTED dependencies.
        
        Args:
            request: Plan creation request
            items: Generated plan items
            detected_seeds: Detected seed items from _detect_missing_base_seeds
            
        Returns:
            List of seed items to add to plan (with included=True)
        """
        seed_items = []
        existing_skus = {item.sku for item in items}
        existing_skus.update(seed.sku for seed in detected_seeds)
        created_seeds: Dict[str, PlanItem] = {}
        
        # Recreate seeds with included=True
        for detected_seed in detected_seeds:
            seed_item = await self._create_seed_item(
                sku=detected_seed.sku,
                entity=detected_seed.entity,
                model_code=detected_seed.template.model if detected_seed.template else "UNKNOWN",
                request=request,
                included=True,  # Include in plan
            )
            if seed_item:
                created_seeds[seed_item.sku] = seed_item
        
        seed_items.extend(created_seeds.values())
        
        # Update VARIATION_PRINTED dependencies for included seeds
        for item in items:
            if item.entity != "VARIATION_PRINTED":
                continue
            
            # Extract model, color, size
            for model_req in request.models:
                model_code = model_req.code
                
                for color_code in request.colors:
                    if model_req.sizes:
                        sizes = model_req.sizes
                    else:
                        model_info = self.models_data.get(model_code, {})
                        sizes = model_info.get("allowed_sizes", [])
                    
                    for size in sizes:
                        expected_variation_sku = self.sku_engine.variation_printed(
                            model_code, request.print.code, color_code, size
                        )
                        
                        if item.sku != expected_variation_sku:
                            continue
                        
                        # Update dependencies based on seed inclusion
                        base_variation_sku = self.sku_engine.base_plain(model_code, color_code, size)
                        
                        if base_variation_sku in created_seeds:
                            # Hard dependency on BASE_VARIATION if it's included in the plan
                            if base_variation_sku not in item.hard_dependencies:
                                item.hard_dependencies.append(base_variation_sku)
                            # Remove from soft dependencies if present
                            if base_variation_sku in item.soft_dependencies:
                                item.soft_dependencies.remove(base_variation_sku)
        
        return seed_items

    async def _create_seed_item(
        self,
        sku: str,
        entity: str,
        model_code: str,
        request: PlanNewRequest,
        included: bool,
    ) -> Optional[PlanItem]:
        """
        Create a seed item (BASE_PARENT or BASE_VARIATION).
        
        Args:
            sku: Generated SKU
            entity: Entity type (BASE_PARENT or BASE_VARIATION)
            model_code: Model code
            request: Plan creation request
            included: Whether this seed is included in the plan
            
        Returns:
            Seed plan item, or None if creation fails
        """
        # Determine which template to use
        if entity == "BASE_PARENT":
            # Try BASE_PARENT template first, fallback to PARENT_PRINTED for compatibility
            template_kind = None
            fallback_used = False
            
            if self._template_exists(model_code, TemplateKindEnum.BASE_PARENT):
                template_kind = TemplateKindEnum.BASE_PARENT
            elif self._template_exists(model_code, TemplateKindEnum.PARENT_PRINTED):
                template_kind = TemplateKindEnum.PARENT_PRINTED
                fallback_used = True
        
        elif entity == "BASE_VARIATION":
            # BASE_VARIATION uses BASE_PLAIN template
            template_kind = None
            fallback_used = False
            
            if self._template_exists(model_code, TemplateKindEnum.BASE_PLAIN):
                template_kind = TemplateKindEnum.BASE_PLAIN
        
        else:
            return None
        
        # If template not found - mark as BLOCKED
        if template_kind is None:
            template_ref = {
                "model_code": model_code,
                "template_kind": None,
                "bling_product_id": None,
                "bling_product_sku": None,
            }
            
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                hard_dependencies=[],
                soft_dependencies=[],
                template=PlanItemTemplate(model=model_code, kind="UNKNOWN"),
                status=PlanItemActionEnum.BLOCKED,
                reason="MISSING_TEMPLATE",
                message=f"Template não disponível para {entity} no modelo {model_code}",
                template_ref=template_ref,
                autoseed_candidate=True,
                included=included,
            )
        
        template_payload = self._get_template_payload(model_code, template_kind)
        
        if template_payload is None:
            template_ref = {
                "model_code": model_code,
                "template_kind": template_kind.value,
                "bling_product_id": self.templates_data.get(model_code, {}).get(template_kind.value),
                "bling_product_sku": None,
            }
            
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                hard_dependencies=[],
                soft_dependencies=[],
                template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                status=PlanItemActionEnum.BLOCKED,
                reason="MISSING_TEMPLATE_PAYLOAD",
                message=f"Payload do template indisponível para {model_code}/{template_kind.value}",
                template_ref=template_ref,
                autoseed_candidate=True,
                included=included,
            )
        
        # Get model info for naming
        model_info = self.models_data[model_code]
        model_name = model_info.get("name", model_code)
        
        # Compute payload for seed
        computed_payload = TemplateMerge.merge(
            template_payload,
            sku=sku,
            name=f"{model_name} Base Liso" if entity == "BASE_PARENT" else f"{model_name} Base Liso",
            overrides=request.overrides,
            price=request.models[0].price if request.models else 0,
            model_name=model_name,
            print_name="Base Liso",
        )
        
        template_ref = {
            "model_code": model_code,
            "template_kind": template_kind.value,
            "bling_product_id": self.templates_data.get(model_code, {}).get(template_kind.value),
            "bling_product_sku": template_payload.get("codigo"),
        }
        
        # Determine action based on whether SKU exists in Bling
        existing_product = await self._check_bling_product(sku)
        
        if existing_product is None:
            action = PlanItemActionEnum.CREATE
            reason_text = f"Seed auto-gerado para {entity.lower()}"
        else:
            # Check if needs update
            diff_fields = self._calculate_diff_summary(
                existing_product,
                computed_payload,
                category_override_active=request.overrides.category_override_id is not None,
            )
            
            if diff_fields:
                action = PlanItemActionEnum.UPDATE
                reason_text = f"Seed existente, requer atualização"
            else:
                action = PlanItemActionEnum.NOOP
                reason_text = f"Seed existente e correto"
        
        return PlanItem(
            sku=sku,
            entity=entity,
            action=action,
            hard_dependencies=[],
            soft_dependencies=[],
            template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
            status=action,
            reason="AUTO_SEED" if not existing_product else None,
            message=reason_text,
            warnings=[],
            diff_summary=[],
            existing_product=existing_product,
            template_ref=template_ref,
            computed_payload_preview=computed_payload,
            autoseed_candidate=True,
            included=included,
        )

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

    def resolve_template_for_entity(
        self, entity: str, model_code: str
    ) -> tuple[Optional[TemplateKindEnum], bool]:
        """
        Resolve the template kind to use for an entity.
        
        Args:
            entity: Entity type (BASE_PLAIN, PARENT_PRINTED, VARIATION_PRINTED)
            model_code: Model code
            
        Returns:
            Tuple of (template_kind, fallback_used)
            - template_kind: The template kind to use, or None if not found
            - fallback_used: Whether a fallback template was used
        """
        if entity == "PARENT_PRINTED":
            # PARENT_PRINTED always uses PARENT_PRINTED template
            if self._template_exists(model_code, TemplateKindEnum.PARENT_PRINTED):
                return TemplateKindEnum.PARENT_PRINTED, False
            return None, False

        if entity == "BASE_PLAIN":
            # BASE_PLAIN always uses BASE_PLAIN template
            if self._template_exists(model_code, TemplateKindEnum.BASE_PLAIN):
                return TemplateKindEnum.BASE_PLAIN, False
            return None, False

        if entity == "VARIATION_PRINTED":
            # VARIATION_PRINTED tries VARIATION_PRINTED first, then falls back to BASE_PLAIN
            if self._template_exists(model_code, TemplateKindEnum.VARIATION_PRINTED):
                return TemplateKindEnum.VARIATION_PRINTED, False
            
            if self._template_exists(model_code, TemplateKindEnum.BASE_PLAIN):
                return TemplateKindEnum.BASE_PLAIN, True
            
            # No template found
            return None, False

        return None, False

    def _template_exists(self, model_code: str, template_kind: TemplateKindEnum) -> bool:
        """
        Check if a template exists (synchronously, from cached templates_data).
        
        Args:
            model_code: Model code
            template_kind: Template kind
            
        Returns:
            True if template exists
        """
        if model_code not in self.templates_data:
            return False
        return template_kind.value in self.templates_data[model_code]

    def _get_dependencies_for_entity(
        self, entity: str, model_code: str, print_code: str, color_code: Optional[str] = None, size: Optional[str] = None
    ) -> tuple[List[str], List[str]]:
        """
        Get hard and soft dependencies for an entity.
        
        Args:
            entity: Entity type
            model_code: Model code
            print_code: Print code
            color_code: Color code (for VARIATION_PRINTED)
            size: Size (for VARIATION_PRINTED)
            
        Returns:
            Tuple of (hard_dependencies, soft_dependencies)
        """
        hard_deps = []
        soft_deps = []

        if entity == "PARENT_PRINTED":
            # No dependencies
            pass

        elif entity == "BASE_PLAIN":
            # No dependencies
            pass

        elif entity == "VARIATION_PRINTED":
            # Hard: PARENT_PRINTED must exist
            parent_sku = self.sku_engine.parent_printed(model_code, print_code)
            hard_deps.append(parent_sku)
            
            # Soft: BASE_PLAIN is recommended but not blocking
            if color_code and size:
                base_sku = self.sku_engine.base_plain(model_code, color_code, size)
                soft_deps.append(base_sku)

        return hard_deps, soft_deps

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
            
            hard_deps, soft_deps = self._get_dependencies_for_entity(
                "PARENT_PRINTED", model_code, print_code
            )
            
            parent_item = await self._create_plan_item(
                sku=parent_sku,
                entity="PARENT_PRINTED",
                model_code=model_code,
                hard_dependencies=hard_deps,
                soft_dependencies=soft_deps,
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
                    # BASE_PLAIN reference as soft dependency
                    base_sku = self.sku_engine.base_plain(model_code, color_code, size)

                    # Create VARIATION_PRINTED item
                    variation_sku = self.sku_engine.variation_printed(
                        model_code, print_code, color_code, size
                    )
                    variation_name = f"{model_name} {print_name} {color_name} {size}"
                    
                    hard_deps, soft_deps = self._get_dependencies_for_entity(
                        "VARIATION_PRINTED", model_code, print_code, color_code, size
                    )
                    
                    variation_item = await self._create_plan_item(
                        sku=variation_sku,
                        entity="VARIATION_PRINTED",
                        model_code=model_code,
                        hard_dependencies=hard_deps,
                        soft_dependencies=soft_deps,
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
        hard_dependencies: List[str],
        soft_dependencies: List[str],
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
            hard_dependencies: List of required dependent SKUs
            soft_dependencies: List of optional recommended SKUs
            
        Returns:
            Plan item with status
        """
        template_kind, fallback_used = self.resolve_template_for_entity(entity, model_code)

        template_payload = None
        if template_kind:
            template_payload = self._get_template_payload(model_code, template_kind)

        template_ref = {
            "model_code": model_code,
            "template_kind": template_kind.value if template_kind else None,
            "bling_product_id": self.templates_data.get(model_code, {}).get(template_kind.value if template_kind else None),
            "bling_product_sku": template_payload.get("codigo") if template_payload else None,
        }

        # If template not found → BLOCKED
        if template_kind is None:
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                hard_dependencies=hard_dependencies,
                soft_dependencies=soft_dependencies,
                template=PlanItemTemplate(model=model_code, kind="UNKNOWN"),
                status=PlanItemActionEnum.BLOCKED,
                reason="MISSING_TEMPLATE",
                message=f"No template available for {entity} in model {model_code}",
                template_ref=template_ref,
            )

        if template_payload is None:
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                hard_dependencies=hard_dependencies,
                soft_dependencies=soft_dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                status=PlanItemActionEnum.BLOCKED,
                reason="MISSING_TEMPLATE_PAYLOAD",
                message=f"Template payload unavailable for {model_code}/{template_kind.value}",
                template_ref=template_ref,
            )

        # Check hard dependencies existence
        missing_hard_deps = []
        for hard_dep in hard_dependencies:
            existing_hard = await self._check_bling_product(hard_dep)
            if existing_hard is None:
                missing_hard_deps.append(hard_dep)

        if missing_hard_deps:
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.BLOCKED,
                hard_dependencies=hard_dependencies,
                soft_dependencies=soft_dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                status=PlanItemActionEnum.BLOCKED,
                reason="MISSING_HARD_DEPENDENCY",
                message=f"Hard dependency ausente: {', '.join(missing_hard_deps)}",
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

        # Calculate warnings (soft dependencies)
        warnings = []
        missing_soft_deps = []
        for soft_dep in soft_dependencies:
            existing = await self._check_bling_product(soft_dep)
            if existing is None:
                missing_soft_deps.append(soft_dep)

        if missing_soft_deps and entity == "VARIATION_PRINTED":
            warnings.append("Base lisa não encontrada (dependência recomendada)")

        # Check if SKU exists in Bling
        existing_product = await self._check_bling_product(sku)

        if existing_product is None:
            # SKU doesn't exist - CREATE
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.CREATE,
                hard_dependencies=hard_dependencies,
                soft_dependencies=soft_dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                status=PlanItemActionEnum.CREATE,
                warnings=warnings,
                diff_summary=[],
                template_ref=template_ref,
                overrides_used=overrides_used,
                computed_payload_preview=computed_payload,
            )

        # SKU exists - check if needs update
        diff_fields = self._calculate_diff_summary(
            existing_product,
            computed_payload,
            category_override_active=overrides.category_override_id is not None,
        )

        if diff_fields:
            return PlanItem(
                sku=sku,
                entity=entity,
                action=PlanItemActionEnum.UPDATE,
                hard_dependencies=hard_dependencies,
                soft_dependencies=soft_dependencies,
                template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                status=PlanItemActionEnum.UPDATE,
                warnings=warnings,
                diff_summary=diff_fields,
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
            hard_dependencies=hard_dependencies,
            soft_dependencies=soft_dependencies,
            template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
            status=PlanItemActionEnum.NOOP,
            warnings=warnings,
            diff_summary=[],
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
        diff_fields = self._calculate_diff_summary(
            existing_product, computed_payload, category_override_active=category_override_active
        )
        return len(diff_fields) > 0

    def _calculate_diff_summary(
        self,
        existing_product: Dict[str, Any],
        computed_payload: Dict[str, Any],
        *,
        category_override_active: bool,
    ) -> List[str]:
        """
        Calculate which fields differ between existing product and computed payload.
        
        Args:
            existing_product: Current product data from Bling
            computed_payload: New payload that would be sent
            category_override_active: Whether category override is active
            
        Returns:
            List of field names that differ
        """
        diff_fields = []

        if not existing_product:
            return ["*"]  # Indicate complete change

        # Fields we always compare
        fields_to_compare = [
            ("preco", "preco"),
            ("nome", "nome"),
            ("precoVenda", "precoVenda"),
            ("descricaoCurta", "descricaoCurta"),
            ("descricaoComplementar", "descricaoComplementar"),
        ]

        for existing_field, computed_field in fields_to_compare:
            expected = computed_payload.get(computed_field)
            actual = existing_product.get(existing_field)
            
            if expected is None:
                continue
            if actual != expected:
                diff_fields.append(existing_field)

        if category_override_active:
            expected_cat = computed_payload.get("categoria_id")
            actual_cat = existing_product.get("categoria_id")
            if expected_cat is not None and actual_cat != expected_cat:
                diff_fields.append("categoria_id")

        return diff_fields

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
