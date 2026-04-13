#!/usr/bin/env python3
"""Diagnose 502 error on production backend."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("=" * 70)
print("SMARTBLING BACKEND 502 DIAGNOSIS")
print("=" * 70)

# 1. Check environment variables
print("\n[1] Environment Configuration:")
required_vars = ['DATABASE_URL', 'SECRET_KEY', 'BLING_CLIENT_ID', 'BLING_CLIENT_SECRET']
for var in required_vars:
    val = os.getenv(var, "NOT SET")
    if val == "NOT SET":
        print(f"  [WARN] {var}: NOT SET")
    else:
        print(f"  [OK] {var}: {val[:20]}..." if len(val) > 20 else f"  [OK] {var}: {val}")

# 2. Test database connection
print("\n[2] Database Connection:")
try:
    from app.settings import settings
    from sqlalchemy import create_engine, text
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(f"  [OK] Connected to: {settings.DATABASE_URL.split('@')[0]}...")
except Exception as e:
    print(f"  [ERROR] Database connection failed: {e}")
    sys.exit(1)

# 3. Check if order_tags table exists
print("\n[3] Database Schema (Tags tables):")
try:
    with engine.connect() as conn:
        # Check if table exists
        if "postgresql" in settings.DATABASE_URL:
            query = "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='order_tags')"
        else:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name='order_tags'"
        
        result = conn.execute(text(query))
        exists = result.fetchone()
        if exists and exists[0]:
            print("  [OK] order_tags table exists")
        else:
            print("  [WARN] order_tags table does NOT exist - migration may not have run")
            # List all tables
            if "postgresql" in settings.DATABASE_URL:
                query = "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            else:
                query = "SELECT name FROM sqlite_master WHERE type='table'"
            result = conn.execute(text(query))
            tables = [row[0] for row in result.fetchall()]
            print(f"  Available tables: {', '.join(tables)}")
except Exception as e:
    print(f"  [ERROR] Schema check failed: {e}")

# 4. Test FastAPI app initialization
print("\n[4] FastAPI App Initialization:")
try:
    from app.main import create_app
    app = create_app()
    print("  [OK] FastAPI app created successfully")
    
    # Check routes
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    auth_routes = [r for r in routes if '/auth' in r]
    print(f"  [OK] Total routes: {len(routes)}")
    print(f"  [OK] Auth routes: {len(auth_routes)}")
    if not auth_routes:
        print("  [ERROR] No auth routes found!")
except Exception as e:
    print(f"  [ERROR] FastAPI initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Test AccessRepository
print("\n[5] Access Control Repository:")
try:
    from app.repositories.access_repo import AccessRepository
    from app.infra.db import SessionLocal
    db = SessionLocal()
    # Just test we can query without error
    from app.models.database import TenantModel
    tenants = db.query(TenantModel).limit(1).all()
    print(f"  [OK] AccessRepository working, {len(tenants)} tenant(s) found")
    db.close()
except Exception as e:
    print(f"  [ERROR] AccessRepository test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
