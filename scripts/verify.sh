#!/bin/bash
# Verification Script para Sprint 1

echo "🔍 smartBling v2 - Sprint 1 Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅${NC} $1/"
        return 0
    else
        echo -e "${RED}❌${NC} $1/"
        return 1
    fi
}

total=0
passed=0

echo "📁 Project Structure"
echo "===================="

# Root files
for file in "README.md" "QUICKSTART.md" "DEVELOPMENT.md" "EXAMPLES.md" "SPRINT1_SUMMARY.md" ".gitignore" "PROJECT_STRUCTURE.md"; do
    check_file "$file" && ((passed++))
    ((total++))
done

echo ""
echo "📁 Backend Files"
echo "================"

# Backend files
for file in "backend/requirements.txt" "backend/.env.example" "backend/run.py" "backend/setup.sh" "backend/setup.bat" "backend/docker-compose.yml" "backend/celery_worker.py"; do
    check_file "$file" && ((passed++))
    ((total++))
done

echo ""
echo "📁 Backend App Structure"
echo "======================="

# App structure
for dir in "backend/app" "backend/app/api" "backend/app/domain" "backend/app/infra" "backend/app/models" "backend/app/repositories" "backend/app/workers" "backend/alembic" "backend/tests"; do
    check_dir "$dir" && ((passed++))
    ((total++))
done

echo ""
echo "📁 App Python Files"
echo "===================="

# App Python files
for file in "backend/app/__init__.py" "backend/app/main.py" "backend/app/settings.py" \
            "backend/app/api/__init__.py" "backend/app/api/auth.py" "backend/app/api/jobs.py" \
            "backend/app/domain/__init__.py" \
            "backend/app/infra/__init__.py" "backend/app/infra/db.py" "backend/app/infra/redis.py" "backend/app/infra/bling_client.py" "backend/app/infra/logging.py" \
            "backend/app/models/__init__.py" "backend/app/models/database.py" "backend/app/models/schemas.py" \
            "backend/app/repositories/__init__.py" "backend/app/repositories/bling_token_repo.py" "backend/app/repositories/job_repo.py" \
            "backend/app/workers/__init__.py" "backend/app/workers/celery_app.py" "backend/app/workers/tasks.py"; do
    check_file "$file" && ((passed++))
    ((total++))
done

echo ""
echo "📁 Migration Files"
echo "=================="

# Alembic files
for file in "backend/alembic/env.py" "backend/alembic/script.py.mako" "backend/alembic/alembic.ini" \
            "backend/alembic/versions/__init__.py" "backend/alembic/versions/001_initial_schema.py"; do
    check_file "$file" && ((passed++))
    ((total++))
done

echo ""
echo "📁 Test Files"
echo "=============="

# Test files
for file in "backend/tests/__init__.py" "backend/tests/test_integration.py"; do
    check_file "$file" && ((passed++))
    ((total++))
done

echo ""
echo "=========================================="
echo "📊 Summary: $passed/$total files verified"
echo "=========================================="

if [ $passed -eq $total ]; then
    echo -e "${GREEN}✅ All files present!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some files are missing${NC}"
    exit 1
fi
