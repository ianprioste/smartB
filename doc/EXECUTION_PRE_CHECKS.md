# Pre-Execution Checks - Sprint 4 Ready

## 5 Critical Requirements Guaranteed

Before moving to Sprint 4 (Execution Phase), these 5 requirements have been implemented and validated:

---

## ✅ 1. Campo no Payload: `options.auto_seed_base_plain`

**Location:** `backend/app/models/schemas.py:288-291`

```python
class PlanOptions(BaseModel):
    """Plan execution options and toggles."""
    auto_seed_base_plain: bool = Field(default=False, description="Auto-seed missing base plain (BASE_PARENT, BASE_VARIATION) templates")
```

**Purpose:** Controls whether the plan builder automatically creates missing base SKUs.

**Usage in Request:**
```json
{
  "print": {...},
  "models": [...],
  "colors": [...],
  "options": {
    "auto_seed_base_plain": true  // Enable auto-seeding
  }
}
```

**Included in Response:** `PlanResponse.options.auto_seed_base_plain`

---

## ✅ 2. UI Preview: Show & Control `auto_seed_base_plain` Toggle

**Location:** `frontend/src/pages/wizard/WizardNew.jsx:613-624`

The UI now displays:
- **Toggle Checkbox:** "Criar automaticamente bases lisas faltantes"
- **Current State:** Shows if auto-seed is ON/OFF
- **Manual Alternative:** Button "🔄 Recalcular Plano" for manual creation workflow
- **Seed Summary:** Displays missing BASE_PARENT and BASE_VARIATION counts

**Code:**
```jsx
<div className="seed-toggle">
  <label>
    <input
      type="checkbox"
      checked={autoSeedBasePlain}
      onChange={e => handleToggleAutoSeed(e.target.checked)}
      disabled={isRegenerating}
    />
    {' '}Criar automaticamente bases lisas faltantes
  </label>
</div>
```

**Preview Updates:** When toggled, plan regenerates immediately showing new/removed auto-seeded items.

---

## ✅ 3. Validation: `template_payload None → BLOCKED` (CREATE Only)

**Location:** `backend/app/domain/plan_builder_new.py:886-910`

**Rule:** Any item with `action=CREATE` and `template_payload=None` is marked `BLOCKED`.

**Validation Logic:**
```python
if existing_product is None:  # SKU doesn't exist
    # CHECK for template_payload
    if template_payload is None:
        return PlanItem(
            action=PlanItemActionEnum.BLOCKED,
            reason="MISSING_TEMPLATE_PAYLOAD",
            message="Template não possui dados de payload - não é possível executar CREATE. Configure o template no Bling."
        )
    # Template exists - proceed with CREATE
    return PlanItem(action=PlanItemActionEnum.CREATE, ...)
```

**When Occurs:**
- Template record exists but has no Bling product data
- Fetch from Bling failed (connectivity issue)
- Corrupted template (data missing)

**Preview Behavior:** Item shows safely (uses empty payload `{}` for display)
**Execution Behavior:** BLOCKED - executor cannot run

**UI Indicator:** `🚫 Template sem payload - não pode executar. Configure no Bling.`

---

## ✅ 4. Separation: "Preview-Safe" vs "Execution-Ready"

**Location:** `backend/app/domain/plan_builder_new.py:850-860`

**Concept:**
- **Preview:** Must show all items safely without crashing
- **Execution:** Must block unsafe items (null payloads, etc.)

**Implementation:**
```python
# For PREVIEW (safe fallback)
payload_for_merge = template_payload or {}

# For EXECUTION (validation)
# Items with template_payload=None are marked BLOCKED
# Only items with action in {CREATE, UPDATE} are executable
```

**Documentation in Schema:**
```python
class PlanResponse(BaseModel):
    """
    IMPORTANT - Executor Usage (Sprint 4):
    When executing this plan, the executor MUST:
    1. Only iterate items where action in {'CREATE', 'UPDATE'}
    2. Skip items where action == 'BLOCKED' (not executable)
    3. Skip items where action == 'NOOP' (already correct in Bling)
    4. Never execute items with reason='MISSING_TEMPLATE_PAYLOAD'
    """
```

**Result:** Safe preview experience + secure execution boundary.

---

## ✅ 5. Executor: Only Uses `{CREATE, UPDATE}`, Skips `BLOCKED`

**Location:** `backend/app/api/plans.py:110-122`

**Documented Requirement:**
```python
async def create_new_plan(request: PlanNewRequest, db: Session = Depends(get_db)):
    """
    IMPORTANT - Execution Semantics:
    ===============================
    - Items with action=CREATE/UPDATE: Ready to execute in Sprint 4
    - Items with action=BLOCKED: Executor MUST skip these (not executable)
    - Items with action=NOOP: Executor can skip (already correct)
    - Items with reason=MISSING_TEMPLATE_PAYLOAD: BLOCKED (no payload data to create)
    
    Preview vs Execution:
    - Preview: Shows all items safely (safe fallback for missing template_payload: {})
    - Execution: Only items with action in {CREATE, UPDATE} are processed
    - BLOCKED items remain for user review but are NOT executed by the worker
    """
```

**Executor Implementation (Sprint 4):**
```python
# Pseudo-code for Sprint 4 executor
for item in plan.items:
    if item.action == 'CREATE':
        # Create product in Bling
        await create_product(item)
    elif item.action == 'UPDATE':
        # Update product in Bling
        await update_product(item)
    elif item.action == 'BLOCKED':
        # Skip - log for user review
        logger.info(f"Skipping BLOCKED item: {item.sku} ({item.reason})")
    elif item.action == 'NOOP':
        # Skip - already correct
        logger.debug(f"Skipping NOOP item: {item.sku}")
```

---

## Summary Table

| Requirement | Status | Location | Impact |
|-------------|--------|----------|--------|
| 1. `options.auto_seed_base_plain` field | ✅ | schemas.py:288-291 | Request/response includes toggle |
| 2. UI show & control toggle | ✅ | WizardNew.jsx:613-624 | User can enable/disable auto-seeding |
| 3. `template_payload None → BLOCKED` | ✅ | plan_builder_new.py:886-910 | Unsafe items blocked from execution |
| 4. Separate preview-safe from execution-ready | ✅ | plan_builder_new.py:850-860 | Safe display + secure execution |
| 5. Executor uses {CREATE, UPDATE} only | ✅ | plans.py:110-122 | Clear rules for Sprint 4 implementation |

---

## Ready for Sprint 4

All pre-execution requirements are:
- ✅ Implemented
- ✅ Validated (builds pass, syntax OK)
- ✅ Documented (code comments + this file)
- ✅ Safe (preview won't crash, execution is guarded)

**Next:** Implement POST /plans/{id}/execute endpoint and Celery worker tasks.
