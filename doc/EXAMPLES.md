"""Example scripts and integration tests."""

# ============ Example 1: OAuth2 Flow ============
# curl -X POST http://localhost:8000/auth/bling/connect
# 
# Response:
# {
#   "authorization_url": "https://bling.com.br/oauth/authorize?..."
# }
# 
# Then visit the URL and authorize, it will callback to:
# http://localhost:8000/auth/bling/callback?code=XXX&state=YYY


# ============ Example 2: Create and Process Job ============
# Step 1: Create a job
# curl -X POST http://localhost:8000/jobs \
#   -H "Content-Type: application/json" \
#   -d '{
#     "type": "sync_products",
#     "input_payload": {"action": "full_sync"},
#     "metadata": {"source": "manual"}
#   }'
#
# Response:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "type": "sync_products",
#   "status": "QUEUED",
#   ...
# }
#
# Step 2: Check status
# curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000
#
# Step 3: View job details with items
# curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/detail


# ============ Example 3: Python Integration ============
import asyncio
from app.infra.bling_client import BlingClient
from datetime import datetime, timedelta


async def example_bling_api_call():
    """Example of using BlingClient."""
    
    # Get token from database
    # from app.repositories.bling_token_repo import BlingTokenRepository
    # token_record = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    
    client = BlingClient(
        access_token="YOUR_TOKEN",
        refresh_token="YOUR_REFRESH_TOKEN",
        token_expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    
    try:
        # Get products from Bling
        products = await client.get("/products", params={"limit": 10})
        print(f"Got {len(products)} products")
        
        # Create a product
        new_product = await client.post("/products", {
            "name": "Test Product",
            "description": "A test product",
            "price": 99.99,
            "sku": "TEST-SKU-001"
        })
        print(f"Created product: {new_product}")
        
    finally:
        client.close()


# Run example
# if __name__ == "__main__":
#     asyncio.run(example_bling_api_call())
