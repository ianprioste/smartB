@echo off
REM Verification Script for Sprint 1 (Windows)

echo 🔍 smartBling v2 - Sprint 1 Verification
echo ==========================================
echo.

setlocal enabledelayedexpansion
set total=0
set passed=0

echo 📁 Project Structure
echo ====================

for %%F in (README.md QUICKSTART.md DEVELOPMENT.md EXAMPLES.md SPRINT1_SUMMARY.md .gitignore PROJECT_STRUCTURE.md) do (
    if exist "%%F" (
        echo [OK] %%F
        set /a passed+=1
    ) else (
        echo [FAIL] %%F
    )
    set /a total+=1
)

echo.
echo 📁 Backend Files
echo ================

for %%F in (backend\requirements.txt backend\.env.example backend\run.py backend\setup.bat backend\docker-compose.yml backend\celery_worker.py) do (
    if exist "%%F" (
        echo [OK] %%F
        set /a passed+=1
    ) else (
        echo [FAIL] %%F
    )
    set /a total+=1
)

echo.
echo 📁 Backend Directories
echo =======================

for %%D in (backend\app backend\app\api backend\app\domain backend\app\infra backend\app\models backend\app\repositories backend\app\workers backend\alembic backend\tests) do (
    if exist "%%D" (
        echo [OK] %%D\
        set /a passed+=1
    ) else (
        echo [FAIL] %%D\
    )
    set /a total+=1
)

echo.
echo ==========================================
echo Summary: %passed%/%total% verified
echo ==========================================

if %passed% equ %total% (
    echo ✅ All files present!
    exit /b 0
) else (
    echo ❌ Some files are missing
    exit /b 1
)

endlocal
