#!/usr/bin/env python
"""Mock Bling client for testing event sales endpoint locally."""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID, uuid4

# Run this to manually test the event sales endpoint with mocked Bling data
# Usage: python test_events_mock.py

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.repositories.bling_token_repo import BlingTokenRepository
from app.models.schemas import SalesEventCreateRequest, SalesEventProductResponse
from app.api.events import (
    _fetch_orders_for_period, 
    _extract_order_items, 
    _match_event_items,
    _canonical_sku,
    _normalize_sku,
)


# Mock Bling responses - these are realistic structures
MOCK_ORDERS = [
    {
        "id": 1001,
        "numero": "PED-001",
        "data": "2024-03-01T10:00:00",
        "totalProdutos": 1000.00,
        "total": 1000.00,
        "situacao": {"nome": "Finalizado"},
        "contato": {"nome": "Cliente A"},
        "itens": [
            {
                "item": {
                    "codigo": "SKU-001",
                    "descricao": "Produto 1",
                    "quantidade": 2,
                    "valor": 500.00,
                    "valorTotal": 1000.00,
                }
            }
        ]
    },
    {
        "id": 1002,
        "numero": "PED-002",
        "data": "2024-03-02T14:30:00",
        "totalProdutos": 1500.00,
        "total": 1500.00,
        "situacao": {"nome": "Finalizado"},
        "contato": {"nome": "Cliente B"},
        "itens": [
            {
                "item": {
                    "codigo": "SKU-002",
                    "descricao": "Produto 2",
                    "quantidade": 3,
                    "valor": 500.00,
                    "valorTotal": 1500.00,
                }
            }
        ]
    },
    {
        "id": 1003,
        "numero": "PED-003",
        "data": "2024-03-03T08:15:00",
        "totalProdutos": 2000.00,
        "total": 2000.00,
        "situacao": {"nome": "Finalizado"},
        "contato": {"nome": "Cliente C"},
        "itens": [
            {
                "item": {
                    "codigo": "SKU-001",
                    "descricao": "Produto 1",
                    "quantidade": 1,
                    "valor": 500.00,
                    "valorTotal": 500.00,
                }
            },
            {
                "item": {
                    "codigo": "SKU-003",
                    "descricao": "Produto 3",
                    "quantidade": 3,
                    "valor": 500.00,
                    "valorTotal": 1500.00,
                }
            }
        ]
    },
    {
        "id": 1004,
        "numero": "PED-004",
        "data": "2024-03-04T16:45:00",
        "totalProdutos": 800.00,
        "total": 800.00,
        "situacao": {"nome": "Cancelado"},
        "contato": {"nome": "Cliente D"},
        "itens": []  # No items in list payload - would need detail fetch
    },
]


async def test_events_system():
    """Create a test event and verify sales filtering."""
    db = SessionLocal()
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        # Create a test event
        print("Creating test event...")
        event = SalesEventRepository.create(
            db=db,
            tenant_id=tenant_id,
            name="Test Event - March",
            start_date=datetime(2024, 3, 1),
            end_date=datetime(2024, 3, 31),
            products=[
                {"sku": "SKU-001", "bling_product_id": None, "product_name": "Produto 1"},
                # NOTE: SKU-003 is implicit child of SKU-001 for this test
            ]
        )
        print(f"✓ Event created: {event.id}")
        
        # Simulate order fetch
        print("\nSimulating order fetch (Phase 1: list payload)...")
        
        # Process mock orders like the real endpoint does
        selected_skus = {"SKU-001"}
        selected_skus_canonical = {_canonical_sku(sku) for sku in selected_skus}
        selected_product_ids = set()
        
        matched_count = 0
        for order in MOCK_ORDERS:
            items = _extract_order_items(order)
            print(f"\nOrder {order['numero']}: extracted {len(items)} items from list payload")
            for item in items:
                print(f"  - {item['sku']}: {item['product_name']}")
            
            matched = _match_event_items(items, selected_skus_canonical, selected_product_ids)
            if matched:
                matched_count += len(matched)
                print(f"  ✓ {len(matched)} item(s) matched event criteria")
        
        print(f"\n✓ Phase 1 complete: {matched_count} items matched from {len(MOCK_ORDERS)} orders")
        print(f"  Note: Order PED-004 has empty itens[] so would require Phase 2 detail fetch")
        
    finally:
        db.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Event Sales Mock Test")
    print("=" * 60)
    asyncio.run(test_events_system())
    print("\n" + "=" * 60)
    print("Test complete!")
