#!/usr/bin/env python
"""
Complete simulation of user flow with API call tracking.
This helps identify where excessive API calls are happening.
"""
import asyncio
import time
from datetime import datetime, timedelta
from uuid import UUID
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient


class CallTracker:
    """Tracks all API calls."""
    
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        self.original_BlingClient_get = BlingClient.get
        BlingClient.get = self._tracked_get
    
    async def _tracked_get(self, self_ref, path: str, **kwargs):
        """Intercept all BlingClient.get calls."""
        start = time.time()
        call_info = {
            "path": path,
            "params": kwargs.get("params", {}),
            "type": "unknown",
        }
        
        # Determine call type
        if "/pedidos/vendas" in path:
            if "/{" in path or path.endswith("}"):
                call_info["type"] = "order-detail-fetch"
            else:
                call_info["type"] = "order-list-fetch"
        elif "/produtos/" in path:
            call_info["type"] = "product-detail-fetch"
        
        try:
            result = await self.original_BlingClient_get(self_ref, path, **kwargs)
            call_info["status"] = "success"
            call_info["duration"] = time.time() - start
            self.calls.append(call_info)
            return result
        except Exception as e:
            call_info["status"] = "error"
            call_info["error"] = str(e)
            call_info["duration"] = time.time() - start
            self.calls.append(call_info)
            raise
    
    def print_summary(self):
        """Print summary of API calls."""
        print("\n" + "="*70)
        print("📡 API CALL ANALYSIS")
        print("="*70)
        
        print(f"\nTotal calls: {len(self.calls)}\n")
        
        # Group by type
        by_type = {}
        for call in self.calls:
            ctype = call["type"]
            if ctype not in by_type:
                by_type[ctype] = []
            by_type[ctype].append(call)
        
        total_duration = 0
        for ctype, calls in sorted(by_type.items()):
            duration = sum(c["duration"] for c in calls)
            total_duration += duration
            print(f"{ctype}: {len(calls)} calls ({duration:.2f}s)")
        
        print(f"\nTotal time: {total_duration:.2f}s")
        
        # Detailed log
        print(f"\n--- Detailed Log ---")
        for i, call in enumerate(self.calls, 1):
            status_icon = "✅" if call["status"] == "success" else "❌"
            path = call["path"]
            duration = call["duration"]
            
            # Shorten path for readability
            if "/pedidos/vendas/" in path and path[-1].isdigit():
                path_display = f"/pedidos/vendas/{path.split('/')[-1]}"
            else:
                path_display = path
            
            print(f"{i}. {status_icon} {path_display} ({duration:.2f}s)")
        
        # Problem diagnosis
        print(f"\n--- DIAGNOSIS ---")
        
        order_details = len([c for c in self.calls if c["type"] == "order-detail-fetch"])
        order_lists = len([c for c in self.calls if c["type"] == "order-list-fetch"])
        
        if order_details == 0:
            print(f"\n✅ GOOD: No order detail fetches needed!")
            print(f"   Items were extracted from list payload (Phase 1 only)")
        else:
            print(f"\n⚠️  WARNING: {order_details} order detail fetches!")
            print(f"   This indicates items are NOT in the list payload")
            print(f"   System falls back to Phase 2 for each order")
            print(f"   Total overhead: {order_details} extra API calls")
        
        return total_duration


async def simulate_user_flow():
    """Simulate complete user workflow with tracking."""
    
    # Setup tracking
    tracker = CallTracker()
    
    db = SessionLocal()
    
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print("\n" + "="*70)
        print("🎯 SIMULATING USER FLOW")
        print("="*70)
        
        # Step 1: Get or create event
        print("\n1️⃣  Looking for existing events...")
        events = SalesEventRepository.list_by_tenant(db, tenant_id)
        
        if not events:
            print("   ❌ No events found!")
            return
        
        event = events[0]
        products = SalesEventRepository.list_products(db, event.id)
        
        print(f"   ✅ Using event: {event.name}")
        print(f"   Period: {event.start_date} to {event.end_date}")
        print(f"   Products: {len(products)}")
        
        if not products:
            print("   ❌ Event has no products!")
            return
        
        for p in products:
            print(f"     - {p.sku}: {p.product_name}")
        
        # Step 2: Get token
        print(f"\n2️⃣  Getting Bling token...")
        token_row = BlingTokenRepository.get_by_tenant(db, tenant_id)
        
        if not token_row:
            print("   ❌ No Bling token found!")
            return
        
        print(f"   ✅ Token available")
        
        # Step 3: Call the actual filtering endpoint logic
        print(f"\n3️⃣  Filtering sales for event...")
        print(f"   📡 Starting API call tracking...")
        
        def _save_token(a, b, c):
            BlingTokenRepository.create_or_update(
                db=db,
                tenant_id=tenant_id,
                access_token=a,
                refresh_token=b,
                expires_at=c,
            )
        
        client = BlingClient(
            access_token=token_row.access_token,
            refresh_token=token_row.refresh_token,
            token_expires_at=token_row.expires_at,
            on_token_refresh=_save_token,
        )
        
        # Import the actual filtering logic
        from app.api.events import (
            _fetch_orders_for_period,
            _extract_order_items,
            _match_event_items,
            _canonical_sku,
            _normalize_sku,
        )
        
        # Phase 1: Fetch orders
        print(f"\n   Phase 1: Fetching orders...")
        orders = await _fetch_orders_for_period(
            client,
            event.start_date.strftime("%Y-%m-%d"),
            event.end_date.strftime("%Y-%m-%d"),
        )
        print(f"   ✅ Fetched {len(orders)} orders")
        
        # Prepare event criteria
        selected_skus = {_normalize_sku(p.sku) for p in products}
        selected_skus_canonical = {_canonical_sku(sku) for sku in selected_skus}
        selected_product_ids = {
            int(p.bling_product_id)
            for p in products
            if p.bling_product_id is not None
        }
        
        # Phase 1: Extract from list
        print(f"\n   Phase 1: Extracting items from list payloads...")
        phase1_count = 0
        phase2_needed = []
        
        for order in orders:
            items = _extract_order_items(order)
            if items:
                phase1_count += len(items)
            else:
                phase2_needed.append(order)
        
        print(f"   ✅ Extracted {phase1_count} items from {len(orders) - len(phase2_needed)} orders")
        
        # Phase 2: Fetch details for orders without items
        if phase2_needed:
            print(f"\n   Phase 2: Fetching details for {len(phase2_needed)} orders...")
            
            semaphore = asyncio.Semaphore(8)
            
            async def _fetch_detail(order_obj):
                async with semaphore:
                    try:
                        return await client.get(f"/pedidos/vendas/{order_obj.get('id')}")
                    except:
                        return None
            
            await asyncio.gather(*[_fetch_detail(o) for o in phase2_needed])
            print(f"   ✅ Fetched details")
        else:
            print(f"\n   Phase 2: Not needed (all orders have items in list)")
        
        await client.client.aclose()
        
        # Print summary
        total_time = tracker.print_summary()
        
        print(f"\n" + "="*70)
        print("RECOMMENDATIONS")
        print("="*70)
        
        order_details = len([c for c in tracker.calls if c["type"] == "order-detail-fetch"])
        
        if order_details > 10:
            print(f"\n❌ PROBLEM IDENTIFIED:")
            print(f"   {order_details} order detail fetches is TOO MANY")
            print(f"   This means Phase 2 is being heavily used")
            print(f"   Root cause: Bling /pedidos/vendas list likely doesn't include items")
            print(f"\n💡 SOLUTION OPTIONS:")
            print(f"   1. Verify if Bling includes 'itens' in list response")
            print(f"   2. Add more intelligent fetching (pagination/windowing)")
            print(f"   3. Consider caching order details locally")
        elif order_details == 0:
            print(f"\n✅ SYSTEM WORKING CORRECTLY:")
            print(f"   All items extracted from list (Phase 1 only)")
            print(f"   Zero detail fetches needed")
        else:
            print(f"\n⚠️  ACCEPTABLE but could optimize:")
            print(f"   {order_details} detail fetches for {len(orders)} orders")
            print(f"   Reduction: {((len(orders) - order_details - 1) / len(orders) * 100):.0f}%")
        
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(simulate_user_flow())
