#!/usr/bin/env python
"""Test the full event sales endpoint with mocked Bling responses."""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.repositories.bling_token_repo import BlingTokenRepository
from app.models.schemas import SalesEventCreateRequest
from app.api import events

# Simulate realistic Bling API responses
MOCK_ORDERS_RESPONSE = {
    "data": [
        {
            "id": 1001,
            "numero": 1001,
            "data": "2024-03-01T10:00:00",
            "totalProdutos": 1000.00,
            "total": 1000.00,
            "situacao": {"nome": "Finalizado"},
            "contato": {"nome": "Cliente A"},
            "itens": [
                {
                    "item": {
                        "codigo": "SKU-001",
                        "descricao": "Produto Premium 1",
                        "quantidade": 2.0,
                        "valor": 500.00,
                        "valorTotal": 1000.00,
                    }
                }
            ]
        },
        {
            "id": 1002,
            "numero": 1002,
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
                        "quantidade": 3.0,
                        "valor": 500.00,
                        "valorTotal": 1500.00,
                    }
                }
            ]
        },
        {
            "id": 1003,
            "numero": 1003,
            "data": "2024-03-03T08:15:00",
            "totalProdutos": 2000.00,
            "total": 2000.00,
            "situacao": {"nome": "Finalizado"},
            "contato": {"nome": "Cliente C"},
            "itens": [
                {
                    "item": {
                        "codigo": "SKU-001",
                        "descricao": "Produto Premium 1",
                        "quantidade": 1.0,
                        "valor": 500.00,
                        "valorTotal": 500.00,
                    }
                },
                {
                    "item": {
                        "codigo": "SKU-003",
                        "descricao": "Produto 3",
                        "quantidade": 3.0,
                        "valor": 500.00,
                        "valorTotal": 1500.00,
                    }
                }
            ]
        },
        {
            "id": 1004,
            "numero": 1004,
            "data": "2024-03-04T16:45:00",
            "totalProdutos": 800.00,
            "total": 800.00,
            "situacao": {"nome": "Processando"},
            "contato": {"nome": "Cliente D"},
            "itens": []  # Phase 2: order with no items in list - needs detail fetch
        },
        {
            "id": 1005,
            "numero": 1005,
            "data": "2024-03-05T12:00:00",
            "totalProdutos": 3000.00,
            "total": 3000.00,
            "situacao": {"nome": "Finalizado"},
            "contato": {"nome": "Cliente E"},
            "itens": [
                {
                    "item": {
                        "codigo": "SKU-001",
                        "descricao": "Produto Premium 1",
                        "quantidade": 5.0,
                        "valor": 600.00,
                        "valorTotal": 3000.00,
                    }
                }
            ]
        },
    ]
}

# Mock detail response for order 1004
MOCK_ORDER_DETAIL_1004 = {
    "data": {
        "id": 1004,
        "numero": 1004,
        "data": "2024-03-04T16:45:00",
        "totalProdutos": 800.00,
        "total": 800.00,
        "situacao": {"nome": "Processando"},
        "contato": {"nome": "Cliente D"},
        "itens": [
            {
                "item": {
                    "codigo": "SKU-002",
                    "descricao": "Produto 2",
                    "quantidade": 1.0,
                    "valor": 800.00,
                    "valorTotal": 800.00,
                }
            }
        ]
    }
}


class MockBlingClient:
    """Mock Bling client that returns test data."""
    
    def __init__(self):
        self.call_count = 0
        self.detail_fetch_count = 0
    
    async def get(self, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        self.call_count += 1
        print(f"  [Mock API Call {self.call_count}] GET {path}")
        
        if "/pedidos/vendas" in path and params and params.get("pagina") == 1:
            return MOCK_ORDERS_RESPONSE
        elif "/pedidos/vendas/1004" in path:
            self.detail_fetch_count += 1
            print(f"    → Returning detail for order 1004 (detail fetch #{self.detail_fetch_count})")
            return MOCK_ORDER_DETAIL_1004
        elif "/pedidos/vendas" in path and params:
            # Pagination check
            return {"data": []}
        
        return {"data": []}
    
    async def aclose(self):
        pass


async def test_full_event_sales_endpoint():
    """Test the complete event sales endpoint flow."""
    db = SessionLocal()
    original_make_client = events._make_client
    
    # Mock the client maker
    def mock_make_client(db_session):
        return MockBlingClient()
    
    events._make_client = mock_make_client
    
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print("\n" + "=" * 70)
        print("TEST: Full Event Sales Endpoint with Two-Phase Filtering")
        print("=" * 70)
        
        # Create a test event
        print("\n1. Creating test event...")
        event = SalesEventRepository.create(
            db=db,
            tenant_id=tenant_id,
            name="Test Event - March Sales",
            start_date=datetime(2024, 3, 1),
            end_date=datetime(2024, 3, 31),
            products=[
                {"sku": "SKU-001", "bling_product_id": None, "product_name": "Produto Premium 1"},
            ]
        )
        event_id = event.id
        print(f"   ✓ Event created: {event_id}")
        print(f"     Name: {event.name}")
        start_str = event.start_date.strftime("%Y-%m-%d") if hasattr(event.start_date, 'strftime') else str(event.start_date)
        end_str = event.end_date.strftime("%Y-%m-%d") if hasattr(event.end_date, 'strftime') else str(event.end_date)
        print(f"     Period: {start_str} to {end_str}")
        
        # Get the event response
        print("\n2. Fetching event response...")
        event_response = events._map_event_response(db, event)
        print(f"   ✓ Event has {len(event_response.products)} product(s)")
        for p in event_response.products:
            print(f"     - {p.sku}: {p.product_name}")
        
        # Call the endpoint logic
        print("\n3. Simulating /events/{event_id}/sales call...")
        print("   Phase 1: Extracting items from order list payloads...")
        
        selected_skus = {
            events._normalize_sku(p.sku)
            for p in event_response.products
            if events._normalize_sku(p.sku)
        }
        selected_skus_canonical = {events._canonical_sku(sku) for sku in selected_skus if sku}
        selected_product_ids = {
            int(p.bling_product_id)
            for p in event_response.products
            if p.bling_product_id is not None
        }
        
        print(f"   Selected SKUs (canonical): {selected_skus_canonical}")
        print(f"   Selected Product IDs: {selected_product_ids}")
        
        # Fetch orders
        client = MockBlingClient()
        orders = await events._fetch_orders_for_period(
            client,
            event.start_date.strftime("%Y-%m-%d"),
            event.end_date.strftime("%Y-%m-%d"),
        )
        print(f"\n   Orders in period: {len(orders)}")
        
        # Phase 1 processing
        filtered_order_map = {}
        orders_needing_detail = []
        matched_items_count = 0
        total_matched = 0.0
        
        for order in orders:
            order_items_from_list = events._extract_order_items(order)
            if order_items_from_list:
                matched = events._match_event_items(order_items_from_list, selected_skus_canonical, selected_product_ids)
                if matched:
                    matched_items = [events.EventMatchedItemResponse(**item) for item in matched]
                    order_total_matched = sum(item.total for item in matched_items)
                    matched_items_count += len(matched_items)
                    total_matched += order_total_matched
                    
                    situacao = order.get("situacao", {}) if isinstance(order.get("situacao"), dict) else {}
                    key = order.get("id") or order.get("numero")
                    filtered_order_map[key] = events.EventOrderResponse(
                        id=order.get("id"),
                        numero=order.get("numero"),
                        data=order.get("data"),
                        cliente=(order.get("contato", {}) or {}).get("nome") or order.get("nomeCliente") or "—",
                        situacao=situacao.get("nome") if isinstance(situacao, dict) else str(order.get("situacao") or "—"),
                        total_order=events._to_float(order.get("totalProdutos") or order.get("total")),
                        total_matched=order_total_matched,
                        matched_items=matched_items,
                    )
                    print(f"     ✓ {order.get('numero')}: {len(matched_items)} item(s) match → R$ {order_total_matched:.2f}")
            else:
                if order.get("id"):
                    orders_needing_detail.append(order)
                    print(f"     ⚠ {order.get('numero')}: No items in list payload → Phase 2 detail fetch needed")
        
        print(f"\n   Phase 1 Result: {matched_items_count} items from {len(filtered_order_map)} orders")
        print(f"   Phase 2 Needed: {len(orders_needing_detail)} order(s) require detail fetch")
        
        # Phase 2 processing
        if orders_needing_detail:
            print("\n   Phase 2: Fetching details for orders without items in list...")
            
            semaphore = asyncio.Semaphore(8)
            
            async def _fetch_detail(order_obj):
                order_id = order_obj.get("id")
                try:
                    async with semaphore:
                        detail = await client.get(f"/pedidos/vendas/{order_id}")
                    return order_obj, detail, None
                except Exception as exc:
                    return order_obj, None, exc
            
            detail_results = await asyncio.gather(*[_fetch_detail(order) for order in orders_needing_detail])
            
            for order, detail, detail_error in detail_results:
                if detail_error is None and detail is not None:
                    order_items = events._extract_order_items(detail)
                    matched = events._match_event_items(order_items, selected_skus_canonical, selected_product_ids)
                    
                    if matched:
                        matched_items = [events.EventMatchedItemResponse(**item) for item in matched]
                        order_total_matched = sum(item.total for item in matched_items)
                        matched_items_count += len(matched_items)
                        total_matched += order_total_matched
                        
                        situacao = order.get("situacao", {}) if isinstance(order.get("situacao"), dict) else {}
                        key = order.get("id") or order.get("numero")
                        filtered_order_map[key] = events.EventOrderResponse(
                            id=order.get("id"),
                            numero=order.get("numero"),
                            data=order.get("data"),
                            cliente=(order.get("contato", {}) or {}).get("nome") or order.get("nomeCliente") or "—",
                            situacao=situacao.get("nome") if isinstance(situacao, dict) else str(order.get("situacao") or "—"),
                            total_order=events._to_float(order.get("totalProdutos") or order.get("total")),
                            total_matched=order_total_matched,
                            matched_items=matched_items,
                        )
                        print(f"     ✓ {order.get('numero')}: {len(matched_items)} item(s) found in detail → R$ {order_total_matched:.2f}")
                    else:
                        print(f"     ✗ {order.get('numero')}: Retrieved detail but no matching items")
        
        filtered_orders = list(filtered_order_map.values())
        
        print("\n" + "=" * 70)
        print("RESULT SUMMARY")
        print("=" * 70)
        print(f"Total orders in period: {len(orders)}")
        print(f"Matching orders: {len(filtered_orders)}")
        print(f"Unique items matched: {matched_items_count}")
        print(f"Total revenue matched: R$ {total_matched:.2f}")
        print(f"Total API calls made: {client.call_count}")
        print(f"Detail fetches needed: {client.detail_fetch_count}")
        print(f"\nOrders matching event criteria:")
        for order in sorted(filtered_orders, key=lambda x: x.numero or ""):
            print(f"  - {order.numero} ({order.cliente}): {len(order.matched_items)} item(s), R$ {order.total_matched:.2f}")
        
        print("\n✓ Test complete - no timeouts or errors!")
        
    finally:
        events._make_client = original_make_client
        db.close()


if __name__ == '__main__':
    asyncio.run(test_full_event_sales_endpoint())
