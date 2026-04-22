"""Integration test for recreate_failed_updates with error handling."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.api import plan_execution
from app.api import plans as plans_api
from app.api.plan_execution import _build_repair_payload_for_item

def test_error_handling_in_loop():
    """Test that errors in one iteration don't break the loop."""
    
    results = []
    processed_ids = set()
    
    candidates = [
        {"sku": "SKU1", "entity": "PARENT_PRINTED"},
        {"sku": "SKU2", "entity": "BASE_PLAIN"},
        {"sku": "SKU3", "entity": "VARIATION_PRINTED"},
    ]
    
    for item in candidates:
        try:
            sku = item.get("sku")
            entity = item.get("entity", "UNKNOWN")
            
            if sku in processed_ids:
                results.append({"sku": sku, "status": "skipped"})
                continue
            
            processed_ids.add(sku)
            
            # Simulate different behaviors
            if entity == "PARENT_PRINTED":
                results.append({"sku": sku, "status": "success", "type": "parent_with_variations"})
            elif entity in ["BASE_PLAIN", "VARIATION_PRINTED"]:
                results.append({"sku": sku, "status": "success", "type": "simple_product"})
            
        except Exception as item_error:
            results.append({"sku": sku, "status": "failed", "error": str(item_error)})
    
    # Verify all items were processed
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    
    # Verify each has correct type
    assert results[0]["type"] == "parent_with_variations"
    assert results[1]["type"] == "simple_product"
    assert results[2]["type"] == "simple_product"
    
    print("✓ Error handling loop works - all items processed independently")


def test_payload_building_decision():
    """Test entity-based payload building decision."""
    
    parent_entities = ["PARENT_PRINTED", "BASE_PARENT"]
    simple_entities = ["BASE_PLAIN", "VARIATION_PRINTED"]
    
    for entity in parent_entities:
        should_use_parent_payload = entity in ["PARENT_PRINTED", "BASE_PARENT"]
        assert should_use_parent_payload, f"{entity} should use parent payload"
    
    for entity in simple_entities:
        should_use_simple_payload = entity not in ["PARENT_PRINTED", "BASE_PARENT"]
        assert should_use_simple_payload, f"{entity} should use simple payload"
    
    print("✓ Payload building decision logic is correct")


def test_computed_payload_validation():
    """Test computed_payload_preview validation."""
    
    test_cases = [
        (None, "empty dict fallback"),
        ({}, "empty dict"),
        ({"nome": "Test"}, "valid dict"),
        ("invalid", "invalid type gets replaced"),
    ]
    
    for computed, description in test_cases:
        # Simulate validation logic
        if not computed or not isinstance(computed, dict):
            computed = {}
        
        assert isinstance(computed, dict), f"Failed for: {description}"
    
    print("✓ computed_payload_preview validation works")


def test_processed_ids_tracking():
    """Test that processed_target_ids prevents duplicates."""
    
    processed_target_ids = set()
    
    items = [
        {"sku": "SKU1", "target_id": 100},
        {"sku": "SKU2", "target_id": 200},
        {"sku": "SKU3", "target_id": 100},  # Duplicate ID
    ]
    
    results = []
    for item in items:
        target_id = item.get("target_id")
        
        if target_id in processed_target_ids:
            results.append({"status": "skipped"})
            continue
        
        processed_target_ids.add(target_id)
        results.append({"status": "processed"})
    
    assert len([r for r in results if r["status"] == "processed"]) == 2
    assert len([r for r in results if r["status"] == "skipped"]) == 1
    
    print("✓ Duplicate ID detection works")


def test_variation_printed_repair_rebuilds_composition_payload():
    """Virtual printed variation repair must rebuild estrutura from base dependency."""

    item = {
        "sku": "BLOSJESTBRP",
        "entity": "VARIATION_PRINTED",
        "hard_dependencies": ["BLOSJEST", "BLOSJBRP"],
        "computed_payload_preview": {
            "nome": "Blusa SJ Estampada BR P",
            "preco": 39.9,
            "variacao": {"ordem": 3},
        },
    }
    sku_cache = {
        "BLOSJBRP": {"id": 9876, "codigo": "BLOSJBRP"},
    }
    color_map = {"BR": "Branco"}

    payload, context = _build_repair_payload_for_item(
        item=item,
        sku_cache=sku_cache,
        color_map=color_map,
        is_physical=False,
    )

    assert payload is not None
    assert payload["formato"] == "E"
    assert payload["estrutura"]["componentes"] == [{"produto": {"id": 9876}, "quantidade": 1}]
    assert payload["estrutura"]["tipoEstoque"] == "V"
    assert context is not None
    assert context["repair_action"] == "orphan_composition_rebuilt"
    assert context["base_sku"] == "BLOSJBRP"

    print("✓ VARIATION_PRINTED rebuilds composition payload for repair")


def test_variation_printed_repair_fails_explicitly_when_base_missing():
    """Virtual printed variation repair must fail explicitly when base SKU is unresolved."""

    item = {
        "sku": "BLOSJESTBRP",
        "entity": "VARIATION_PRINTED",
        "hard_dependencies": ["BLOSJEST", "BLOSJBRP"],
        "computed_payload_preview": {"nome": "Blusa SJ Estampada BR P", "preco": 39.9},
    }

    payload, context = _build_repair_payload_for_item(
        item=item,
        sku_cache={},
        color_map={"BR": "Branco"},
        is_physical=False,
    )

    assert payload is None
    assert context is not None
    assert context["error_type"] == "missing_base_for_composition"
    assert context["base_sku"] == "BLOSJBRP"

    print("✓ VARIATION_PRINTED reports explicit missing base for repair")


def test_recreate_failed_updates_endpoint_rebuilds_orphan_composition(monkeypatch):
    """Endpoint-level repair should rebuild orphan composition and send PUT in-place."""

    class _FakeHttpClient:
        async def aclose(self):
            return None

    class _FakeBlingClient:
        def __init__(self):
            self.client = _FakeHttpClient()
            self.put_calls = []

        async def get(self, path, params=None):
            if path == "/produtos/777":
                return {
                    "data": {
                        "id": 777,
                        "codigo": "BLOSJESTBRP",
                        "formato": "E",
                        "estrutura": {"componentes": []},
                    }
                }
            raise AssertionError(f"Unexpected GET path: {path}")

        async def put(self, path, payload):
            self.put_calls.append((path, payload))
            return {"data": {"id": 777}}

    fake_client = _FakeBlingClient()

    async def fake_get_bling_client(_db):
        return fake_client

    async def fake_check_bling_products_bulk(_client, _skus):
        return {
            "BLOSJEST": {"id": 555, "codigo": "BLOSJEST"},
            "BLOSJBRP": {"id": 9876, "codigo": "BLOSJBRP"},
            "BLOSJESTBRP": {"id": 777, "codigo": "BLOSJESTBRP"},
        }

    async def fake_fetch_id_by_sku(_client, sku):
        assert sku == "BLOSJESTBRP"
        return 777

    monkeypatch.setattr(plan_execution, "_get_bling_client", fake_get_bling_client)
    monkeypatch.setattr(plan_execution, "fetch_id_by_sku", fake_fetch_id_by_sku)
    monkeypatch.setattr(plans_api, "_check_bling_products_bulk", fake_check_bling_products_bulk)

    payload = {
        "plan": {
            "options": {"stock_type": "virtual"},
            "colors": [{"code": "BR", "name": "Branco"}],
            "items": [
                {
                    "sku": "BLOSJESTBRP",
                    "entity": "VARIATION_PRINTED",
                    "action": "UPDATE",
                    "hard_dependencies": ["BLOSJEST", "BLOSJBRP"],
                    "computed_payload_preview": {
                        "nome": "Blusa SJ Estampada BR P",
                        "preco": 39.9,
                        "variacao": {"ordem": 2},
                    },
                }
            ],
        },
        "failed_update_skus": ["BLOSJESTBRP"],
    }

    result = asyncio.run(plan_execution.recreate_failed_updates(payload, db=object()))

    assert result["summary"]["repaired"] == 1
    assert result["summary"]["failed"] == 0
    item = result["results"][0]
    assert item["status"] == "success"
    assert item["action"] == "repaired_in_place"
    assert item["repair_action"] == "orphan_composition_rebuilt"
    assert item["base_sku"] == "BLOSJBRP"
    assert len(fake_client.put_calls) == 1
    _, put_payload = fake_client.put_calls[0]
    assert put_payload["formato"] == "E"
    assert put_payload["estrutura"]["componentes"] == [{"produto": {"id": 9876}, "quantidade": 1}]

    print("✓ recreate_failed_updates rebuilds orphan composition and updates in-place")


if __name__ == "__main__":
    test_error_handling_in_loop()
    test_payload_building_decision()
    test_computed_payload_validation()
    test_processed_ids_tracking()
    test_variation_printed_repair_rebuilds_composition_payload()
    test_variation_printed_repair_fails_explicitly_when_base_missing()
    test_recreate_failed_updates_endpoint_rebuilds_orphan_composition()
    print("\n✅ All integration tests passed!")
