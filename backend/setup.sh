#!/bin/bash
# Setup script for smartBling v2 backend

set -e

echo "🚀 smartBling v2 - Backend Setup"
echo "=================================="

# Check Python version
python_version=$(python --version | cut -d' ' -f2)
echo "✅ Python version: $python_version"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Copy .env if doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your Bling credentials"
else
    echo "✅ .env already exists"
fi

# Create database tables
echo ""
echo "🗄️  Setting up database..."
python -c "
from app.models.database import Base
from app.infra.db import engine
Base.metadata.create_all(bind=engine)
print('✅ Database tables created')
"

# Create default tenant
echo ""
echo "👤 Creating default tenant..."
python -c "
from sqlalchemy.orm import sessionmaker
from app.infra.db import engine
from app.repositories.bling_token_repo import BlingTokenRepository
Session = sessionmaker(bind=engine)
session = Session()
BlingTokenRepository.get_or_create_default_tenant(session)
print('✅ Default tenant created')
"

echo ""
echo "=================================="
echo "✅ Setup completed!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Bling OAuth2 credentials"
echo "2. Start services: docker-compose up -d"
echo "3. Run server: python run.py"
echo "4. Run worker: celery -A app.workers.celery_app worker --loglevel=info"
echo ""
