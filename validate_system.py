#!/usr/bin/env python
"""
Quick validation script to ensure all components are in place.
Run this before deploying to production.
"""
import os
import sys
from pathlib import Path


def check_backend_files():
    """Verify all backend files exist."""
    print("\n📁 Backend Files:")
    files = [
        "backend/app/api/events.py",
        "backend/app/repositories/sales_event_repo.py",
        "backend/alembic/versions/004_sales_events.py",
        "backend/test_events_suite.py",
        "backend/test_events_full.py",
    ]
    
    all_exist = True
    for file in files:
        exists = os.path.exists(file)
        status = "✅" if exists else "❌"
        print(f"  {status} {file}")
        if not exists:
            all_exist = False
    
    return all_exist


def check_frontend_files():
    """Verify all frontend files exist."""
    print("\n📁 Frontend Files:")
    files = [
        "frontend/src/pages/events/EventCreatePage.jsx",
        "frontend/src/pages/events/EventSalesPage.jsx",
    ]
    
    all_exist = True
    for file in files:
        exists = os.path.exists(file)
        status = "✅" if exists else "❌"
        print(f"  {status} {file}")
        if not exists:
            all_exist = False
    
    return all_exist


def check_documentation():
    """Verify documentation files exist."""
    print("\n📚 Documentation:")
    files = [
        "SALES_EVENTS_README.md",
        "doc/SALES_EVENTS_IMPLEMENTATION.md",
        "SYSTEM_COMPLETION_SUMMARY.md",
    ]
    
    all_exist = True
    for file in files:
        exists = os.path.exists(file)
        status = "✅" if exists else "❌"
        print(f"  {status} {file}")
        if not exists:
            all_exist = False
    
    return all_exist


def main():
    """Run all checks."""
    print("\n" + "="*70)
    print("🔍 SYSTEM VALIDATION CHECKLIST")
    print("="*70)
    
    backend_ok = check_backend_files()
    frontend_ok = check_frontend_files()
    docs_ok = check_documentation()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    backend_status = "✅ All backend files present" if backend_ok else "❌ Missing backend files"
    frontend_status = "✅ All frontend files present" if frontend_ok else "❌ Missing frontend files"
    docs_status = "✅ All documentation present" if docs_ok else "❌ Missing documentation"
    
    print(f"\n{backend_status}")
    print(f"{frontend_status}")
    print(f"{docs_status}")
    
    if backend_ok and frontend_ok and docs_ok:
        print("\n✅ SYSTEM READY FOR TESTING/DEPLOYMENT\n")
        print("Next steps:")
        print("  1. cd backend && python test_events_suite.py")
        print("  2. python run.py  (start backend)")
        print("  3. Open http://localhost:5173 (frontend)")
        print("  4. Menu → 🎪 Eventos de Vendas\n")
        return 0
    else:
        print("\n❌ SYSTEM INCOMPLETE - Files missing\n")
        return 1


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    sys.exit(main())
