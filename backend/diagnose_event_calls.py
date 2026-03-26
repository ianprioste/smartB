#!/usr/bin/env python
"""
Diagnostic script to debug excessive API calls when filtering event sales.
Logs all API calls and analyzes the Bling response structure.
"""
import asyncio
import time
from datetime import datetime, timedelta
from uuid import UUID
from typing import Dict, Any, List

from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository
from app.infra.bling_client import BlingClient
from app.repositories.bling_token_repo import BlingTokenRepository


class DiagnosticBlingClient(BlingClient):
    """BlingClient wrapper that logs all API calls."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_log: List[Dict[str, Any]] = []
        self.original_get = self.get
        self.get = self._logged_get
    
    async def _logged_get(self, path: str, params: Dict = None, **kwargs):
        """Log the API call and then execute it."""
        call_info = {
            "timestamp": datetime.now(),
            "path": path,
            "params": params,
            "start_time": time.time(),
        }
        
        try:
            result = await self.original_get(path, params=params, **kwargs)
            call_info["status"] = "success"
            call_info["duration"] = time.time() - call_info["start_time"]
            
            # Log response structure for /pedidos/vendas
            if "/pedidos/vendas" in path and not path.endswith('}'):
                data = result.get("data", [])
                if data:
                    first_obj = data[0] if isinstance(data, list) else data
                    call_info["first_obj_keys"] = list(first_obj.keys()) if isinstance(first_obj, dict) else "not-dict"
                    has_itens = "itens" in first_obj if isinstance(first_obj, dict) else False
                    call_info["has_itens"] = has_itens
                    
            self.call_log.append(call_info)
            return result
        except Exception as e:
            call_info["status"] = "error"
            call_info["error"] = str(e)
            call_info["duration"] = time.time() - call_info["start_time"]
            self.call_log.append(call_info)
            raise


async def diagnose_event_filtering():
    """Run diagnostic on event filtering to identify API call issues."""
    db = SessionLocal()
    
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print("\n" + "="*70)
        print("🔍 DIAGNOSTIC: Event Sales Filtering API Calls")
        print("="*70)
        
        # Get first event
        events = SalesEventRepository.list_by_tenant(db, tenant_id)
        if not events:
            print("\n❌ No events found. Create an event first!")
            return
        
        event = events[0]
        products = SalesEventRepository.list_products(db, event.id)
        
        print(f"\n📋 Event Details:")
        print(f"  Event ID: {event.id}")
        print(f"  Name: {event.name}")
        print(f"  Period: {event.start_date} to {event.end_date}")
        print(f"  Products: {len(products)}")
        for p in products[:3]:
            print(f"    - {p.sku}: {p.product_name}")
        
        # Get Bling token and create diagnostic client
        token_row = BlingTokenRepository.get_by_tenant(db, tenant_id)
        if not token_row:
            print("\n❌ No Bling token found. Authenticate first!")
            return
        
        def _save_token(access_token, refresh_token, expires_at):
            BlingTokenRepository.create_or_update(
                db=db,
                tenant_id=tenant_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
            )
        
        # Use diagnostic client to log all calls
        client = DiagnosticBlingClient(
            access_token=token_row.access_token,
            refresh_token=token_row.refresh_token,
            token_expires_at=token_row.expires_at,
            on_token_refresh=_save_token,
        )
        
        print(f"\n🔄 Fetching orders for period: {event.start_date} to {event.end_date}")
        
        # Fetch orders
        start = time.time()
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
        print(f"\n✅ Fetched {len(orders)} orders in {time.time() - start:.2f}s")
        
        # Analyze response structure
        if orders:
            first_order = orders[0]
            print(f"\n📊 First Order Structure:")
            print(f"  Keys: {list(first_order.keys())}")
            
            has_itens = "itens" in first_order
            print(f"  Has 'itens' field: {has_itens}")
            
            if has_itens:
                itens = first_order.get("itens", [])
                print(f"  Items in list: {len(itens)}")
                if itens:
                    print(f"    First item keys: {list(itens[0].keys())}")
            else:
                print(f"  ⚠️  No items field! Will need detail fetch for each order")
        
        # Check if detail fetches are needed
        orders_without_itens = sum(1 for o in orders if not o.get("itens"))
        print(f"\n⚠️  Orders without items in list: {orders_without_itens}/{len(orders)}")
        print(f"   → Would require {orders_without_itens} additional API calls!")
        
        # Log all API calls made
        print(f"\n📡 API Calls Made:")
        print(f"  Total: {len(client.call_log)}")
        
        for i, call in enumerate(client.call_log, 1):
            path = call["path"]
            status = call["status"]
            duration = call["duration"]
            params = call.get("params", {})
            
            if params:
                params_str = ", ".join(f"{k}={v}" for k, v in params.items() if k != "pagina")
            else:
                params_str = "detail-fetch"
            
            status_icon = "✅" if status == "success" else "❌"
            print(f"  {i}. {status_icon} {path} ({params_str}) - {duration:.2f}s")
            
            if call.get("has_itens") is False:
                print(f"     ⚠️  No items in response!")
        
        # Summary
        try:
            await client.client.aclose()
        except:
            pass
        
        print(f"\n" + "="*70)
        print("ANALYSIS")
        print("="*70)
        
        if orders_without_itens == 0:
            print(f"\n✅ GOOD NEWS: All {len(orders)} orders have items in list!")
            print(f"   Only {len(client.call_log)} API call needed = Phase 1 only")
            print(f"   Problem might be elsewhere...")
        elif orders_without_itens == len(orders):
            print(f"\n❌ PROBLEM: ALL {len(orders)} orders missing items!")
            print(f"   This will require {len(orders)+1} API calls total")
            print(f"   Solution: Need to fetch details for all orders")
            print(f"   OR: Change Bling query to include items")
        else:
            phase2_calls = orders_without_itens
            total_calls = 1 + phase2_calls
            print(f"\n⚠️  PARTIAL: {orders_without_itens}/{len(orders)} need detail fetch")
            print(f"   Total API calls: {total_calls} (vs {len(orders)} if sequential)")
            print(f"   Current approach: {((len(orders) - total_calls) / len(orders) * 100):.0f}% reduction")
        
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(diagnose_event_filtering())
