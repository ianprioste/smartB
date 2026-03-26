#!/usr/bin/env python
"""Quick diagnostic script to inspect Bling API response structure."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from uuid import UUID
from app.infra.db import SessionLocal
from app.repositories.bling_token_repo import BlingTokenRepository
from app.infra.bling_client import BlingClient
import json


async def main():
    db = SessionLocal()
    try:
        token = BlingTokenRepository.get_by_tenant(
            db, 
            UUID('00000000-0000-0000-0000-000000000001')
        )
        if not token:
            print("ERROR: No Bling token found")
            return

        def save_token(a, b, c): pass
        
        client = BlingClient(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            token_expires_at=token.expires_at,
            on_token_refresh=save_token,
        )

        print("Fetching sample orders from Bling...")
        resp = await client.get('/pedidos/vendas', params={'pagina': 1, 'limite': 2})
        
        if resp.get('data'):
            sample_order = resp['data'][0]
            print("\n=== Order Keys ===")
            print(sorted(sample_order.keys()))
            
            print("\n=== Order Sample ===")
            print(json.dumps({
                k: sample_order.get(k) 
                for k in ['id', 'numero', 'data', 'total', 'totalProdutos', 'contato', 'situacao', 'itens']
            }, indent=2, default=str))
            
            if sample_order.get('itens'):
                print("\n=== First Item Keys ===")
                first_item = sample_order['itens'][0]
                if isinstance(first_item, dict):
                    print(sorted(first_item.keys()))
                    print("\n=== First Item Sample ===")
                    print(json.dumps(first_item, indent=2, default=str)[:500])
        
        await client.client.aclose()
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
