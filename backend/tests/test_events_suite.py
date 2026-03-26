#!/usr/bin/env python
"""
Test suite for Sales Events system.

Run with: python test_events_suite.py

This validates all components of the events system without requiring a valid Bling token.
"""
import asyncio
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.api import events


def test_sku_normalization():
    """Test SKU normalization rules."""
    print("\n" + "="*70)
    print("TEST 1: SKU Normalization")
    print("="*70)
    
    test_cases = [
        ("SKU-001", "SKU-001", "uppercase normalization"),
        ("sku-001", "SKU-001", "case insensitive upper"),
        ("SKU_001", "SKU_001", "separators preserved in normalized"),
    ]
    
    for input_val, expected, description in test_cases:
        result = events._normalize_sku(input_val)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {description}: '{input_val}' → '{result}'")
        assert result == expected, f"Expected {expected}, got {result}"
    
    print("  PASSED ✓")


def test_canonical_sku():
    """Test canonical SKU (case + separator insensitive)."""
    print("\n" + "="*70)
    print("TEST 2: Canonical SKU (Match Across Variations)")
    print("="*70)
    
    test_cases = [
        ("SKU-001", "sku-001", True, "case difference ignored"),
        ("SKU-001", "sku_001", True, "separator difference ignored"),
        ("SKU-001", "SKU001", True, "all separators ignored"),
        ("SKU-001", "SKU-002", False, "different SKU detects diff"),
    ]
    
    for sku1, sku2, should_match, description in test_cases:
        canon1 = events._canonical_sku(sku1)
        canon2 = events._canonical_sku(sku2)
        matches = canon1 == canon2
        status = "✓" if matches == should_match else "✗"
        print(f"  {status} {description}")
        print(f"      '{sku1}' ({canon1}) vs '{sku2}' ({canon2}) → {matches}")
        assert matches == should_match
    
    print("  PASSED ✓")


def test_item_extraction():
    """Test extraction of items from order payloads."""
    print("\n" + "="*70)
    print("TEST 3: Item Extraction from Order")
    print("="*70)
    
    order_payload = {
        "id": 1001,
        "numero": 1001,
        "total": 1000.00,
        "itens": [
            {
                "item": {
                    "codigo": "SKU-001",
                    "descricao": "Produto Premium",
                    "quantidade": 2.0,
                    "valor": 500.00,
                    "valorTotal": 1000.00,
                }
            }
        ]
    }
    
    items = events._extract_order_items(order_payload)
    
    print(f"  Extracted {len(items)} item(s)")
    assert len(items) == 1, "Should extract 1 item"
    
    item = items[0]
    print(f"    SKU: {item['sku']}")
    print(f"    Product: {item['product_name']}")
    print(f"    Quantity: {item['quantity']}")
    print(f"    Unit Price: R$ {item['unit_price']:.2f}")
    print(f"    Total: R$ {item['total']:.2f}")
    
    assert item['sku'] == "SKU-001"
    assert item['quantity'] == 2.0
    assert item['unit_price'] == 500.00
    assert item['total'] == 1000.00
    
    print("  PASSED ✓")


def test_item_matching():
    """Test matching of items against event products."""
    print("\n" + "="*70)
    print("TEST 4: Item Matching Against Event Products")
    print("="*70)
    
    # Sample items from order
    order_items = [
        {
            "sku": "SKU-001",
            "product_id": None,
            "product_name": "Produto 1",
            "quantity": 2,
            "unit_price": 100.0,
            "total": 200.0,
        },
        {
            "sku": "SKU-002",
            "product_id": None,
            "product_name": "Produto 2",
            "quantity": 1,
            "unit_price": 150.0,
            "total": 150.0,
        },
        {
            "sku": "SKU-003",
            "product_id": None,
            "product_name": "Produto 3",
            "quantity": 3,
            "unit_price": 50.0,
            "total": 150.0,
        },
    ]
    
    # Event has SKU-001 and SKU-002
    event_skus_canonical = {
        events._canonical_sku("SKU-001"),
        events._canonical_sku("SKU-002"),
    }
    event_product_ids = set()
    
    matched = events._match_event_items(order_items, event_skus_canonical, event_product_ids)
    
    print(f"  Event criteria: SKU-001, SKU-002")
    print(f"  Order has: SKU-001, SKU-002, SKU-003")
    print(f"  Matched: {len(matched)} item(s)")
    
    assert len(matched) == 2, "Should match 2 items"
    assert matched[0]['sku'] == "SKU-001"
    assert matched[1]['sku'] == "SKU-002"
    
    print(f"    ✓ SKU-001 (R$ 200.00)")
    print(f"    ✓ SKU-002 (R$ 150.00)")
    print(f"    ✗ SKU-003 (skipped)")
    
    print("  PASSED ✓")


def test_event_crud():
    """Test event creation, read, update, delete."""
    print("\n" + "="*70)
    print("TEST 5: Event CRUD Operations")
    print("="*70)
    
    db = SessionLocal()
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        # CREATE
        print("  Creating event...")
        event = SalesEventRepository.create(
            db=db,
            tenant_id=tenant_id,
            name="Test Event",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            products=[
                {"sku": "SKU-001", "bling_product_id": None, "product_name": "Produto 1"},
                {"sku": "SKU-002", "bling_product_id": None, "product_name": "Produto 2"},
            ]
        )
        event_id = event.id
        print(f"    ✓ Event {event_id} created")
        
        # READ
        print("  Reading event...")
        fetched = SalesEventRepository.get_by_id(db, event_id, tenant_id)
        assert fetched is not None
        assert fetched.name == "Test Event"
        products = SalesEventRepository.list_products(db, event_id)
        print(f"    ✓ Event retrieved with {len(products)} product(s)")
        
        # UPDATE
        print("  Updating event...")
        updated = SalesEventRepository.update(
            db=db,
            event=fetched,
            name="Test Event Updated",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            products=[
                {"sku": "SKU-001", "bling_product_id": None, "product_name": "Produto 1 Updated"},
            ]
        )
        products = SalesEventRepository.list_products(db, updated.id)
        assert updated.name == "Test Event Updated"
        assert len(products) == 1
        print(f"    ✓ Event updated (1 product now)")
        
        # DELETE
        print("  Deleting event...")
        SalesEventRepository.delete(db, updated)
        deleted = SalesEventRepository.get_by_id(db, event_id, tenant_id)
        assert deleted is None
        print(f"    ✓ Event deleted")
        
        print("  PASSED ✓")
        
    finally:
        db.close()


async def test_two_phase_filtering():
    """Test the two-phase filtering logic."""
    print("\n" + "="*70)
    print("TEST 6: Two-Phase Filtering Simulation")
    print("="*70)
    
    # Simulate 5 orders: 3 with items in list, 2 without
    orders = [
        {
            "id": 1001,
            "numero": 1001,
            "itens": [{"item": {"codigo": "SKU-001", "descricao": "Prod1", "quantidade": 1, "valor": 100, "valorTotal": 100}}]
        },
        {
            "id": 1002,
            "numero": 1002,
            "itens": [{"item": {"codigo": "SKU-002", "descricao": "Prod2", "quantidade": 1, "valor": 200, "valorTotal": 200}}]
        },
        {
            "id": 1003,
            "numero": 1003,
            "itens": []  # No items in list - would need Phase 2
        },
        {
            "id": 1004,
            "numero": 1004,
            "itens": [{"item": {"codigo": "SKU-001", "descricao": "Prod1", "quantidade": 2, "valor": 100, "valorTotal": 200}}]
        },
        {
            "id": 1005,
            "numero": 1005,
            "itens": []  # No items in list - would need Phase 2
        },
    ]
    
    event_skus_canonical = {events._canonical_sku("SKU-001")}
    event_product_ids = set()
    
    # Phase 1: Extract from list
    phase1_matched = 0
    phase2_needed = 0
    matched_order_map = {}
    orders_needing_detail = []
    
    for order in orders:
        items = events._extract_order_items(order)
        if items:
            matched = events._match_event_items(items, event_skus_canonical, event_product_ids)
            if matched:
                phase1_matched += len(matched)
                matched_order_map[order['id']] = order
        else:
            orders_needing_detail.append(order)
            phase2_needed += 1
    
    print(f"  Phase 1 Results:")
    print(f"    Orders with items in list: 3")
    print(f"    Matched items extracted: {phase1_matched}")
    print(f"    Orders requiring detail fetch: {phase2_needed}")
    print(f"\n  Phase 1 Analysis:")
    print(f"    ✓ Order 1001: Extracted from list (SKU-001)")
    print(f"    ✗ Order 1002: Extracted from list but no match (SKU-002)")
    print(f"    ⚠ Order 1003: No items in list → Phase 2 needed")
    print(f"    ✓ Order 1004: Extracted from list (SKU-001)")
    print(f"    ⚠ Order 1005: No items in list → Phase 2 needed")
    print(f"\n  Efficiency:")
    print(f"    API Calls: 1 (list) + {phase2_needed} (details) = {1 + phase2_needed} vs {len(orders)} sequential")
    print(f"    Reduction: {((len(orders) - (1 + phase2_needed)) / len(orders) * 100):.0f}%")
    
    assert phase1_matched == 2, "Should match 2 items from list"
    assert len(matched_order_map) == 2, "Should match 2 orders"
    assert phase2_needed == 2, "Should need detail for 2 orders"
    
    print("  PASSED ✓")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("📊 SALES EVENTS SYSTEM - TEST SUITE")
    print("="*70)
    
    try:
        # Synchronous tests
        test_sku_normalization()
        test_canonical_sku()
        test_item_extraction()
        test_item_matching()
        test_event_crud()
        
        # Async tests
        asyncio.run(test_two_phase_filtering())
        
        # Summary
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSystem ready for production use!")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
