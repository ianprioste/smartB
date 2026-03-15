@echo off
REM SmartBling v2 - Starter para Windows
REM Abre 3 terminais: Backend, Frontend, Celery Worker

setlocal enabledelayedexpansion

set PROJECT_ROOT=C:\Github\SmartB

echo.
echo 🚀 Iniciando SmartBling v2 - Ambiente de Desenvolvimento
echo.

REM Terminal 1: Backend API
echo 📡 Abrindo Backend API ^(localhost:8000^)...
start cmd /k "cd /d %PROJECT_ROOT%\backend && %PROJECT_ROOT%\.venv\Scripts\Activate.ps1 -NoExit && python run.py"

timeout /t 2 /nobreak

REM Terminal 2: Frontend Dev Server
echo ⚛️  Abrindo Frontend ^(localhost:5173^)...
start cmd /k "cd /d %PROJECT_ROOT%\frontend && npm run dev"

timeout /t 2 /nobreak

REM Terminal 3: Celery Worker
echo 🔄 Abrindo Celery Worker...
start cmd /k "cd /d %PROJECT_ROOT%\backend && ..\.venv\Scripts\celery.exe -A app.workers.celery_app worker --loglevel=info --pool=solo"

echo.
echo ✅ Todos os servidores foram iniciados em 3 janelas!
echo.
echo 📍 Endpoints:
echo   - Backend API:     http://localhost:8000/docs
echo   - Frontend Admin:  http://localhost:5173
echo   - Celery Worker:   Em execução no 3º terminal
echo.
echo 💡 Feche as janelas ou pressione CTRL+C para parar
echo.
pause
