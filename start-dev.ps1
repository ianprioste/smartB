# SmartB Development Environment Starter
# Starts Backend API, Frontend dev server, Celery worker, and Celery beat.

Write-Host "Starting SmartBling v2 development environment" -ForegroundColor Green
Write-Host ""

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Terminal 1: Backend API
Write-Host "Opening Backend API (localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\backend"
    & "$projectRoot\.venv\Scripts\Activate.ps1"
    Write-Host 'Applying migrations (alembic upgrade head)...' -ForegroundColor Yellow
    ..\.venv\Scripts\alembic.exe upgrade head
    Write-Host 'Backend running at http://localhost:8000/docs' -ForegroundColor Green
    python run.py
    Read-Host 'Press ENTER to close'
"@

Start-Sleep -Seconds 2

# Terminal 2: Frontend Dev Server
Write-Host "Opening Frontend (localhost:5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\frontend"
    Write-Host 'Frontend running at http://localhost:5173' -ForegroundColor Green
    npm run dev
    Read-Host 'Press ENTER to close'
"@

Start-Sleep -Seconds 2

# Terminal 3: Celery Worker
Write-Host "Opening Celery Worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\backend"
    & "$projectRoot\.venv\Scripts\Activate.ps1"
    Write-Host 'Celery Worker running' -ForegroundColor Green
    ..\.venv\Scripts\celery.exe -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
    Read-Host 'Press ENTER to close'
"@

Start-Sleep -Seconds 2

# Terminal 4: Celery Beat (scheduler) must run as a separate process on Windows.
Write-Host "Opening Celery Beat (periodic scheduler)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\backend"
    & "$projectRoot\.venv\Scripts\Activate.ps1"
    Write-Host 'Celery Beat running (incremental sync every 15 minutes)' -ForegroundColor Green
    ..\.venv\Scripts\celery.exe -A app.workers.celery_app:celery_app beat --loglevel=info
    Read-Host 'Press ENTER to close'
"@

Write-Host ""
Write-Host "All services were started." -ForegroundColor Green
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor Yellow
Write-Host "  - Backend API:    http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  - Frontend Admin: http://localhost:5173" -ForegroundColor Gray
Write-Host "  - Celery Worker:  Running in terminal 3" -ForegroundColor Gray
Write-Host "  - Celery Beat:    Running in terminal 4" -ForegroundColor Gray
Write-Host ""
Write-Host "Use CTRL+C in each terminal to stop services." -ForegroundColor Yellow
