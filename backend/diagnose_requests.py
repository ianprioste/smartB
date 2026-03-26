#!/usr/bin/env python
"""
Simple diagnostic to check how many API calls are being made.

Run with: python diagnose_requests.py

This shows:
1. How many orders are in the period
2. How many have items in the list (Phase 1)
3. How many need detail fetch (Phase 2)
4. Total API calls being made
"""
import asyncio
from datetime import datetime
from uuid import UUID
from typing import Dict, Any

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient


async def diagnose():
    """Run diagnosis."""
    db = SessionLocal()
    
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print("\n" + "="*70)
        print("🔍 DIAGNOSTIC: API Calls Analysis")
        print("="*70)
        
        # Get events
        events = SalesEventRepository.list_by_tenant(db, tenant_id)
        
        if not events:
            print("\n❌ No events found!")
            return
        
        print(f"\nFound {len(events)} event(s):\n")
        
        for i, event in enumerate(events, 1):
            print(f"{i}. {event.name} ({event.start_date} to {event.end_date})")
        
        # Prefer event with latest end_date to avoid stale test events.
        event = sorted(events, key=lambda e: (e.end_date, e.created_at), reverse=True)[0]
        products = SalesEventRepository.list_products(db, event.id)
        
        print(f"\n📋 Using event: {event.name}")
        print(f"   Period: {event.start_date} to {event.end_date}")
        print(f"   Products: {len(products)}")
        
        if not products:
            print("   ❌ Event has no products!")
            return
        
        # Get token
        token_row = BlingTokenRepository.get_by_tenant(db, tenant_id)
        
        if not token_row:
            print("\n❌ No Bling token! Please authenticate first.")
            return
        
        # Create client
        def _save(a, b, c):
            BlingTokenRepository.create_or_update(db, tenant_id, a, b, c)
        
        client = BlingClient(
            access_token=token_row.access_token,
            refresh_token=token_row.refresh_token,
            token_expires_at=token_row.expires_at,
            on_token_refresh=_save,
        )
        
        print(f"\n🔄 Calling Bling API...")
        print(f"   GET /pedidos/vendas?dataInicial=...&dataFinal=...")
        
        # Fetch orders
        resp = await client.get(
            "/pedidos/vendas",
            params={
                "dataInicial": event.start_date.strftime("%Y-%m-%d"),
                "dataFinal": event.end_date.strftime("%Y-%m-%d"),
                "pagina": 1,
                "limite": 100,
            }
        )
        
        orders = resp.get("data", []) if isinstance(resp, dict) else []
        print(f"   ✅ Got {len(orders)} orders")
        
        # Analyze
        print(f"\n📊 Analysis:")
        print(f"   Total orders in period: {len(orders)}")
        
        # Check which have items in list
        with_items = sum(1 for o in orders if o.get("itens"))
        without_items = len(orders) - with_items
        
        print(f"   Orders with items in list (Phase 1): {with_items}")
        print(f"   Orders without items (Phase 2): {without_items}")
        
        print(f"\n📡 API Calls:")
        print(f"   Phase 1 (list): 1 call")
        
        if without_items > 0:
            print(f"   Phase 2 (detail): {without_items} calls")
            print(f"   Total: {1 + without_items} calls")
            
            if without_items > 50:
                print(f"\n   ⚠️  WARNING: {without_items} detail fetches!")
                print(f"      This might be slow depending on Bling rate limit")
            elif without_items > 0:
                print(f"\n   ⚠️  NOTICE: {without_items} detail fetches needed")
                print(f"      But manageable with parallelization (Semaphore)")
        else:
            print(f"   Total: 1 call")
            print(f"\n   ✅ OPTIMAL: All items in list!")
        
        # Recommendation
        print(f"\n💡 Recommendation:")

        if len(orders) == 0:
            print("   ⚠️ Inconclusivo: não há pedidos no período desse evento")
            print("      Selecione um evento com vendas para medir Phase 2 corretamente")
        elif without_items == len(orders):
            print(f"   ❌ Problem confirmed: Bling doesn't return items in list")
            print(f"      Contact Bling support about getting items in /pedidos/vendas")
        elif without_items > len(orders) * 0.8:
            print(f"   ⚠️  Most orders need detail fetch")
            print(f"      Consider implementing local caching")
        else:
            print(f"   ✅ System working as designed")
            print(f"      Some detail fetches but mostly from list")
        
        await client.client.aclose()
        
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(diagnose())
