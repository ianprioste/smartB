#!/usr/bin/env python
"""
List all events and show their details with data availability.
"""
from uuid import UUID
from sqlalchemy.orm import Session
from app.infra.db import SessionLocal
from app.repositories.sales_event_repo import SalesEventRepository


def list_all_events():
    """List all events with their details."""
    db = SessionLocal()
    
    try:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")
        
        print("\n" + "="*70)
        print("📋 All Events")
        print("="*70)
        
        events = SalesEventRepository.list_by_tenant(db, tenant_id)
        
        if not events:
            print("\n❌ No events found!\n")
            return
        
        print(f"\nTotal events: {len(events)}\n")
        
        for i, event in enumerate(events, 1):
            products = SalesEventRepository.list_products(db, event.id)
            
            print(f"{i}. Event: {event.name}")
            print(f"   ID: {event.id}")
            print(f"   Period: {event.start_date} to {event.end_date}")
            print(f"   Products: {len(products)}")
            
            for p in products:
                print(f"     - {p.sku}: {p.product_name}")
            
            print()
        
        print("="*70)
        print("\nTo diagnose API calls, use:")
        print("  python diagnose_event_calls.py {event_id}")
        print("\nOr edit the script to use a specific event_id")
        
    finally:
        db.close()


if __name__ == '__main__':
    list_all_events()
