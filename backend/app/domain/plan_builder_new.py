"""Plan Builder for NEW_PRINT - Sprint 3.

This module generates complete execution plans for product creation
without writing anything to Bling.

Responsibilities:
- Validate templates and dependencies
- Generate SKUs using SkuEngine
- Check existing products in Bling (read-only)
- Produce preview with CREATE/UPDATE/NOOP/BLOCKED status
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
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
        bling_cache: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,  # Pre-loaded cache of SKU -> product
    ):
        """
        Initialize plan builder.
        
        Args:
            models_data: Model information {code: {name, allowed_sizes}}
            colors_data: Color information {code: name}
            templates_data: Template information {model_code: {kind: bling_product_id}}
            bling_checker: Async function(sku) -> Optional[Dict] to check Bling
            bling_client: Optional Bling client to fetch template payloads
            bling_cache: Optional pre-loaded cache of SKU -> product to avoid individual checks
        """
        self.models_data = models_data
        self.colors_data = colors_data
        self.templates_data = templates_data
        self.bling_checker = bling_checker
        self.bling_client = bling_client
        self.template_payloads: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.sku_engine = SkuEngine()
        # Cache for Bling product lookups to avoid rate limits
        self._bling_cache: Dict[str, Optional[Dict[str, Any]]] = bling_cache or {}
        # Execution flags (set during plan build)
        self._auto_seed_base_plain: bool = False
        self._planned_base_skus: set[str] = set()

    def collect_all_required_skus(self, request: PlanNewRequest) -> set[str]:
        """
        Collect all SKUs that will be needed for this plan (for bulk Bling check).
        
        This generates all possible SKUs without making any Bling calls,
        useful for pre-loading the cache before building the plan.
        
        Args:
            request: Plan creation request
            
        Returns:
            Set of all SKUs that will be verified during plan building
        """
        required_skus = set()
        
        try:
            logger.debug(f"Collecting SKUs for print={request.print.code}")
            
            # Add all product SKUs (printed products - e.g., CAMINFNOVO)
            for model_req in request.models:
                model_code = model_req.code
                sizes = model_req.sizes or self.models_data.get(model_code, {}).get("allowed_sizes", [])
                
                # Add parent printed SKU (e.g., CAMINFNOVO)
                parent_sku = self.sku_engine.parent_printed(model_code, request.print.code)
                required_skus.add(parent_sku)
                logger.debug(f"Added parent printed SKU: {parent_sku}")
                
                # Add variation printed SKUs for SELECTED colors (plan items).
                for color_code in request.colors:
                    for size in sizes:
                        variation_sku = self.sku_engine.variation_printed(model_code, request.print.code, color_code, size)
                        required_skus.add(variation_sku)
                        logger.debug(f"Added variation printed SKU: {variation_sku}")

                # Also pre-check ALL available colors so we can detect existing
                # variations in Bling that are NOT in the current selection
                # (needed to compute planned_deletions without extra Bling calls).
                for color_code in self.colors_data.keys():
                    if color_code in request.colors:
                        continue  # already added above
                    for size in sizes:
                        extra_sku = self.sku_engine.variation_printed(model_code, request.print.code, color_code, size)
                        required_skus.add(extra_sku)
            
            # Add seed SKUs (base products without print - e.g., CAMINF, CAMINFBR2)
            for model_req in request.models:
                model_code = model_req.code
                sizes = model_req.sizes or self.models_data.get(model_code, {}).get("allowed_sizes", [])
                
                # BASE_PARENT
                base_parent_sku = model_code.upper()
                required_skus.add(base_parent_sku)
                logger.debug(f"Added BASE_PARENT: {base_parent_sku}")
                
                # BASE_VARIATION for each color/size
                for color_code in request.colors:
                    for size in sizes:
                        base_variation_sku = self.sku_engine.base_plain(model_code, color_code, size)
                        required_skus.add(base_variation_sku)
                        logger.debug(f"Added BASE_VARIATION: {base_variation_sku}")
        except Exception as e:
            logger.warning(f"Error collecting required SKUs: {e}")
            return set()
        
        logger.debug(f"Collected {len(required_skus)} total SKUs for bulk check")
        return required_skus

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
        logger.debug(f"Building plan for print {request.print.code}")

        # Execution flags
        self._auto_seed_base_plain = request.options.auto_seed_base_plain
        self._physical_stock = getattr(request.options, 'stock_type', 'virtual') == 'physical'
        self._planned_base_skus = set()

        # Validate input
        self._validate_input(request)

        # Load only the requested model templates from Bling for merging.
        await self._load_template_payloads({model_req.code for model_req in request.models})

        # Pre-register base SKUs that will be created when auto-seed is enabled
        if self._auto_seed_base_plain:
            for model_req in request.models:
                sizes = self._get_model_sizes(model_req)
                for color_code in request.colors:
                    for size in sizes:
                        self._planned_base_skus.add(self.sku_engine.base_plain(model_req.code, color_code, size))

        # Track items to create
        items_to_create = []
        
        # IMPORTANT: Always check if BASE_PARENT exists, regardless of auto_seed_base_plain setting
        # This ensures wizard detects existing bases in all scenarios
        for model_req in request.models:
            base_parent_sku = model_req.code.upper()
            existing_base_parent = await self._check_bling_product_cached(base_parent_sku)
            if existing_base_parent:
                # Base parent exists - mark as NOOP
                base_parent_item = PlanItem(
                    sku=base_parent_sku,
                    entity="BASE_PARENT",
                    action=PlanItemActionEnum.NOOP,
                    hard_dependencies=[],
                    soft_dependencies=[],
                    template=PlanItemTemplate(
                        model=model_req.code,
                        kind=TemplateKindEnum.BASE_PARENT.value,
                        fallback_used=False,
                    ),
                    status=PlanItemActionEnum.NOOP,
                    reason="EXISTING_IN_BLING",
                    message=f"Base {base_parent_sku} já existe no Bling",
                    existing_product=existing_base_parent,
                    template_ref={
                        "model_code": model_req.code,
                        "template_kind": TemplateKindEnum.BASE_PARENT.value,
                    },
                    overrides_used={},
                    autoseed_candidate=True,
                    included=False,
                )
                items_to_create.append(base_parent_item)
                logger.info(f"Found existing BASE_PARENT: {base_parent_sku}")
        
        # If manual mode, verify which seeds user manually created
        # (This checks only seeds that SHOULD exist, not all possible SKUs)
        if not request.options.auto_seed_base_plain:
            all_possible_seeds = await self._get_all_possible_seeds(request)
            verified_manual_seeds = await self._verify_manually_created_seeds(all_possible_seeds)
            # Only add seeds that aren't already detected BASE_PARENT items
            existing_skus = {item.sku for item in items_to_create}
            for seed in verified_manual_seeds:
                if seed.sku not in existing_skus:
                    items_to_create.append(seed)

        # Generate all plan items
        # (Dependencies will be checked on-demand with caching - no bulk verification)
        generated_items = await self._generate_items(request)
        items_to_create.extend(generated_items)

        # Annotate parent UPDATE items with variation SKUs that are expected
        # to be removed when syncing selected colors/sizes.
        await self._annotate_planned_deletions(items_to_create)

        # Detect missing base seeds for seed_summary UI
        detected_missing_seeds = await self._detect_missing_base_seeds(request, items_to_create)
        
        # Build seed_summary with only missing seeds
        seed_summary = SeedSummary()
        
        # Filter out seeds that were verified as existing
        verified_skus = {item.sku for item in items_to_create if hasattr(item, 'autoseed_candidate') and item.autoseed_candidate}
        remaining_missing = [s for s in detected_missing_seeds if s.sku not in verified_skus]
        
        seed_summary.base_parent_missing = [
            item.sku for item in remaining_missing if item.entity == "BASE_PARENT"
        ]
        seed_summary.base_variation_missing = [
            item.sku for item in remaining_missing if item.entity == "BASE_VARIATION"
        ]
        seed_summary.total_missing = len(seed_summary.base_parent_missing) + len(seed_summary.base_variation_missing)
        
        # If auto-seed enabled, add items to plan
        if request.options.auto_seed_base_plain:
            seed_items = await self._add_base_seed_items(request, items_to_create, detected_missing_seeds)
            items_to_create.extend(seed_items)
            seed_summary.total_included = sum(1 for item in seed_items if item.included)

        # Calculate summary
        summary = self._calculate_summary(request, items_to_create)

        # Check for blockers
        has_blockers = any(item.action == PlanItemActionEnum.BLOCKED for item in items_to_create)

        plan = PlanResponse(
            planVersion="1.0",
            type="NEW_PRINT",
            summary=summary,
            items=items_to_create,
            has_blockers=has_blockers,
            seed_summary=seed_summary,
            options=request.options,
        )

        logger.info(
            f"Plan {request.print.code}: {summary.total_skus} SKUs "
            f"(CREATE={summary.create_count}, UPDATE={summary.update_count})"
        )

        return plan

    async def _annotate_planned_deletions(self, items: List[PlanItem]) -> None:
        """Populate planned_deletions purely from the pre-loaded Bling cache.

        Logic: the plan selects specific colors/sizes.  Any variation that
        already EXISTS in Bling (detected by the bulk SKU check) but is NOT
        included in the current selection will be removed when the parent is
        sent to Bling.  We know this entirely from data already in
        _bling_cache — no extra Bling API calls needed.
        """
        for parent_item in items:
            if parent_item.entity != "PARENT_PRINTED":
                continue
            if parent_item.action not in {PlanItemActionEnum.UPDATE, PlanItemActionEnum.NOOP}:
                continue
            # Parent must exist in Bling for a deletion to be possible
            parent_sku_upper = str(parent_item.sku or "").strip().upper()
            if not parent_sku_upper:
                continue

            parent_exists = (
                parent_item.existing_product is not None
                or self._bling_cache.get(parent_sku_upper) is not None
            )
            if not parent_exists:
                continue

            # Derive model_code and print_code from the parent item
            model_code = (parent_item.template.model if parent_item.template else None) or ""
            if not model_code:
                continue
            # print_code is the suffix after model_code in the parent SKU
            model_code_upper = model_code.strip().upper()
            print_code = parent_sku_upper[len(model_code_upper):] if parent_sku_upper.startswith(model_code_upper) else ""
            if not print_code:
                continue

            allowed_sizes: List[str] = self.models_data.get(model_code, {}).get("allowed_sizes", [])
            if not allowed_sizes:
                continue

            # Build the full universe of possible variation SKUs for this parent
            # (all colors × all allowed sizes) and check which ones exist in cache
            selected_skus: Set[str] = set()
            existing_in_bling: Set[str] = set()

            for color_code, _ in self.colors_data.items():
                for size in allowed_sizes:
                    var_sku = self.sku_engine.variation_printed(
                        model_code, print_code, color_code, size
                    )
                    var_sku_upper = var_sku.strip().upper()

                    if self._bling_cache.get(var_sku_upper) is not None or self._bling_cache.get(var_sku) is not None:
                        existing_in_bling.add(var_sku_upper)

            # Selected = variation items in this plan that belong to this parent
            for var_item in items:
                if var_item.entity != "VARIATION_PRINTED":
                    continue
                if var_item.included is False:
                    continue
                var_sku_upper = str(var_item.sku or "").strip().upper()
                # Belongs to this parent if dependency matches OR SKU starts with parent SKU
                has_parent_dep = any(
                    str(dep or "").strip().upper() == parent_sku_upper
                    for dep in (var_item.hard_dependencies or [])
                )
                if has_parent_dep or var_sku_upper.startswith(parent_sku_upper):
                    selected_skus.add(var_sku_upper)

            to_delete = sorted(existing_in_bling - selected_skus)
            logger.info(
                f"planned_deletions for {parent_sku_upper}: "
                f"existing_in_bling={sorted(existing_in_bling)}, "
                f"selected={sorted(selected_skus)}, "
                f"to_delete={to_delete}"
            )
            if to_delete:
                parent_item.planned_deletions = to_delete

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
        # Physical stock doesn't need BASE_PLAIN seeds at all
        if self._physical_stock:
            return []

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
                sizes = self._get_model_sizes(model_req)
                for color_code in request.colors:
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
            sizes = self._get_model_sizes(model_req)
            
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
                existing = await self._check_bling_product_cached(seed.sku)
                
                if existing:
                    # Seed was created manually in Bling - mark as NOOP (não será modificado)
                    verified_seed = PlanItem(
                        sku=seed.sku,
                        entity=seed.entity,
                        action=PlanItemActionEnum.NOOP,
                        hard_dependencies=[],
                        soft_dependencies=[],
                        template=seed.template,
                        status=PlanItemActionEnum.NOOP,
                        reason="MANUALLY_CREATED",
                        message=f"{seed.entity} já existe no Bling (não será modificado)",
                        existing_product=existing,
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
                sizes = self._get_model_sizes(model_req)
                for color_code in request.colors:
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
        
        # If template not found, still create seed using empty payload and BASE_PLAIN
        if template_kind is None:
            template_kind = TemplateKindEnum.BASE_PLAIN
            logger.warning(f"Template ausente para {entity}/{model_code}; usando payload vazio")
        
        # Get template payload; if missing, use empty payload so creation still proceeds
        template_payload = self._get_template_payload(model_code, template_kind) or {}
        
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
            # Bases já existentes não serão modificadas (são apenas dependências)
            action = PlanItemActionEnum.NOOP
            reason_text = f"Seed existente (não será modificado)"
        
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

    def _get_model_sizes(self, model_req) -> List[str]:
        """Return requested sizes or fall back to allowed sizes configured for the model."""
        if model_req.sizes:
            return model_req.sizes
        model_info = self.models_data.get(model_req.code, {})
        return model_info.get("allowed_sizes", [])

    async def _check_bling_product_cached(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Check if product exists in Bling (cached to avoid rate limits).
        
        Args:
            sku: Product SKU
            
        Returns:
            Product data if found, None if not found
        """
        sku_upper = str(sku or "").strip().upper()

        if sku in self._bling_cache:
            cached_value = self._bling_cache[sku]
            if cached_value is not None:
                logger.debug(f"Cache HIT for SKU {sku}: found in Bling")
            else:
                logger.debug(f"Cache HIT for SKU {sku}: NOT found in Bling")
            return cached_value

        # Try normalized (uppercase) lookup as fallback.
        if sku_upper != sku and sku_upper in self._bling_cache:
            cached_value = self._bling_cache[sku_upper]
            logger.debug(f"Cache HIT for SKU {sku} (normalized to {sku_upper}): {'found' if cached_value else 'not found'}")
            return cached_value
        
        # Fetch and cache
        logger.debug(f"Cache MISS for SKU {sku}, calling bling_checker")
        result = await self.bling_checker(sku)
        self._bling_cache[sku] = result
        if sku_upper != sku:
            self._bling_cache[sku_upper] = result
        if result is not None:
            logger.debug(f"Bling check returned product for {sku}: id={result.get('id')}")
        else:
            logger.debug(f"Bling check returned None for {sku}")
        return result

    async def _load_template_payloads(self, model_codes: Optional[Set[str]] = None) -> None:
        """Fetch template payloads from Bling for the requested models only."""
        if not self.bling_client:
            logger.warning("No bling_client provided; template payloads unavailable")
            return

        selected_model_codes = set(model_codes or self.templates_data.keys())
        fetch_jobs: list[tuple[str, str, int]] = []

        for model_code in selected_model_codes:
            kinds = self.templates_data.get(model_code, {})
            if model_code not in self.template_payloads:
                self.template_payloads[model_code] = {}

            for kind, bling_product_id in kinds.items():
                if kind in self.template_payloads[model_code]:
                    continue
                fetch_jobs.append((model_code, kind, bling_product_id))

        if not fetch_jobs:
            return

        payload_results = await asyncio.gather(
            *(self.bling_client.get_product(bling_product_id) for _, _, bling_product_id in fetch_jobs),
            return_exceptions=True,
        )

        for (model_code, kind, _), payload_result in zip(fetch_jobs, payload_results):
            if isinstance(payload_result, Exception):
                logger.warning(
                    f"Failed to fetch template payload for {model_code}/{kind}: {payload_result}"
                )
                self.template_payloads[model_code][kind] = None
                continue

            self.template_payloads[model_code][kind] = payload_result.get("data") if payload_result else None

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
            
            # Hard: BASE_PLAIN must exist to build composition with the base as component
            # Only required for virtual stock; physical stock uses simple variation (no BASE)
            if color_code and size and not getattr(self, '_physical_stock', False):
                base_sku = self.sku_engine.base_plain(model_code, color_code, size)
                hard_deps.append(base_sku)

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
        force_update_id_assigned = False
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

            # If editing by ID, attach force_update_id so execution uses it directly.
            # Apply to only one parent item to avoid cross-updating multiple models
            # with the same target product id.
            edit_parent_id = getattr(request, 'edit_parent_id', None)
            if edit_parent_id and parent_item.action == PlanItemActionEnum.UPDATE and not force_update_id_assigned:
                parent_item.force_update_id = edit_parent_id
                force_update_id_assigned = True

            items.append(parent_item)
            
            # Add parent SKU to cache so VARIATION items don't think it's missing
            # (Parent will be created in this same plan, so it's "available")
            if parent_item.action in [PlanItemActionEnum.CREATE, PlanItemActionEnum.UPDATE]:
                self._bling_cache[parent_sku] = {"codigo": parent_sku}  # Mock as existing

        # Second pass: create VARIATION_PRINTED for each color/size combination
        for model_req in model_codes:
            model_code = model_req.code
            model_info = self.models_data[model_code]
            model_name = model_info.get("name", model_code)
            model_price = model_req.price

            # Determine sizes
            sizes = self._get_model_sizes(model_req)

            # Parent for this model
            parent_sku = self.sku_engine.parent_printed(model_code, print_code)

            for color_code in request.colors:
                color_name = self.colors_data.get(color_code, color_code)
                for size in sizes:
                    # CREATE VARIATION_PRINTED item
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
            available_skus: SKUs already available in Bling or will be created
            
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

        # If no template, use empty payload - item can still be PREVIEWED
        # (User will need to fill in details manually or via overrides)
        if template_kind is None:
            template_kind = TemplateKindEnum.BASE_PLAIN  # Default fallback
            logger.warning(f"No template found for {entity}/{model_code}, using empty payload for preview")
        
        # IMPORTANT: Distinguish between "preview-safe" and "execution-ready"
        # - For PREVIEW: use template_payload or {} (safe fallback, no crash)
        # - For EXECUTION: validation below ensures template_payload exists (CREATE blocked if None)
        payload_for_merge = template_payload or {}

        # Check hard dependencies existence (with caching to avoid rate limits)
        # An item is BLOCKED only if a hard dependency is truly missing in Bling
        missing_hard_deps = []
        for hard_dep in hard_dependencies:
            # Check if it exists in Bling (cached)
            existing_hard = await self._check_bling_product_cached(hard_dep)
            if existing_hard is None:
                missing_hard_deps.append(hard_dep)

        if missing_hard_deps:
            # If auto-seed is enabled, allow base seeds planned for creation to satisfy deps
            if self._auto_seed_base_plain:
                missing_hard_deps = [dep for dep in missing_hard_deps if dep not in self._planned_base_skus]

            # After filtering, if any remain, the item is blocked
            if missing_hard_deps:
                logger.warning(f"Item {sku} BLOCKED: missing hard deps {missing_hard_deps}")
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
            payload_for_merge,
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
        
        logger.info(f"Creating plan item for SKU {sku}: existing_product={'FOUND' if existing_product else 'NOT_FOUND'}")

        if existing_product is None:
            # SKU doesn't exist - CHECK for template_payload
            # IMPORTANT: template_payload None means we can't execute CREATE safely
            # Preview shows it, but execution is BLOCKED to prevent data loss
            if template_payload is None:
                logger.warning(f"Item {sku} (CREATE) BLOCKED: template payload is None - cannot execute without template data")
                return PlanItem(
                    sku=sku,
                    entity=entity,
                    action=PlanItemActionEnum.BLOCKED,
                    hard_dependencies=hard_dependencies,
                    soft_dependencies=soft_dependencies,
                    template=PlanItemTemplate(model=model_code, kind=template_kind.value, fallback_used=fallback_used),
                    status=PlanItemActionEnum.BLOCKED,
                    reason="MISSING_TEMPLATE_PAYLOAD",
                    message="Template não possui dados de payload - não é possível executar CREATE. Configure o template no Bling.",
                    warnings=warnings,
                    diff_summary=[],
                    template_ref=template_ref,
                    overrides_used=overrides_used,
                    computed_payload_preview=computed_payload,
                )
            
            # Template payload exists - can proceed with CREATE
            logger.info(f"Planning CREATE for {sku}")
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
        logger.info(f"SKU {sku} found in Bling (id={existing_product.get('id')}), checking if needs update")
        diff_fields = self._calculate_diff_summary(
            existing_product,
            computed_payload,
            category_override_active=overrides.category_override_id is not None,
        )

        if diff_fields:
            logger.info(f"Planning UPDATE for {sku}: changed fields = {diff_fields}")
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
            return await self._check_bling_product_cached(sku)
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
            ("ncm", "ncm"),
            ("cest", "cest"),
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
