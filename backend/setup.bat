@echo off
REM Setup script for smartBling v2 backend (Windows)

setlocal enabledelayedexpansion

echo 🚀 smartBling v2 - Backend Setup
echo ==================================

REM Check Python version
python --version

REM Install dependencies
echo.
echo 📦 Installing dependencies...
pip install -r requirements.txt

REM Copy .env if doesn't exist
if not exist .env (
    echo.
    echo 📝 Creating .env from template...
    copy .env.example .env
    echo ⚠️  Please edit .env with your Bling credentials
) else (
    echo ✅ .env already exists
)

REM Create database tables
echo.
echo 🗄️  Setting up database...
python -c "from app.models.database import Base; from app.infra.db import engine; Base.metadata.create_all(bind=engine); print('✅ Database tables created')"

REM Create default tenant
echo.
echo 👤 Creating default tenant...
python -c "from sqlalchemy.orm import sessionmaker; from app.infra.db import engine; from app.repositories.bling_token_repo import BlingTokenRepository; Session = sessionmaker(bind=engine); session = Session(); BlingTokenRepository.get_or_create_default_tenant(session); print('✅ Default tenant created')"

echo.
echo ==================================
echo ✅ Setup completed!
echo.
echo Next steps:
echo 1. Edit .env with your Bling OAuth2 credentials
echo 2. Start services: docker-compose up -d
echo 3. Run server: python run.py
echo 4. Run worker: celery -A app.workers.celery_app worker --loglevel=info
echo.

endlocal
