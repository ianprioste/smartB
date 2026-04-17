#!/usr/bin/env python
"""Initialize database tables directly using SQLAlchemy for local testing."""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.absolute()
sys.path.insert(0, str(backend_path))

from app.infra.db import Base, engine

def init_db():
    """Create all tables."""
    print("🗄️  Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

if __name__ == "__main__":
    init_db()
