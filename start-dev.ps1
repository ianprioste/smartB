# SmartB Development Environment Starter
# Inicia Backend API, Frontend dev server e Celery Worker em paralelo

Write-Host "🚀 Iniciando SmartBling v2 - Ambiente de Desenvolvimento" -ForegroundColor Green
Write-Host ""

$projectRoot = "C:\Github\SmartB"

# Terminal 1: Backend API
Write-Host "📡 Abrindo Backend API (localhost:8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\backend"
    & "$projectRoot\.venv\Scripts\Activate.ps1"
    Write-Host '✅ Backend rodando em http://localhost:8000/docs' -ForegroundColor Green
    python run.py
    Read-Host 'Pressione ENTER para fechar'
"@

Start-Sleep -Seconds 2

# Terminal 2: Frontend Dev Server
Write-Host "⚛️  Abrindo Frontend (localhost:5173)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\frontend"
    Write-Host '✅ Frontend rodando em http://localhost:5173' -ForegroundColor Green
    npm run dev
    Read-Host 'Pressione ENTER para fechar'
"@

Start-Sleep -Seconds 2

# Terminal 3: Celery Worker
Write-Host "🔄 Abrindo Celery Worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @"
    Set-Location "$projectRoot\backend"
    & "$projectRoot\.venv\Scripts\Activate.ps1"
    Write-Host '✅ Celery Worker rodando' -ForegroundColor Green
    ..\.venv\Scripts\celery.exe -A app.workers.celery_app worker --loglevel=info --pool=solo
    Read-Host 'Pressione ENTER para fechar'
"@

Write-Host ""
Write-Host "✅ Todos os servidores foram iniciados!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Endpoints:" -ForegroundColor Yellow
Write-Host "  • Backend API:     http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  • Frontend Admin:  http://localhost:5173" -ForegroundColor Gray
Write-Host "  • Celery Worker:   Em execução no 3º terminal" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 Feche os terminais ou pressione CTRL+C em cada um para parar" -ForegroundColor Yellow
