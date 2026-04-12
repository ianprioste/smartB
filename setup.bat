@echo off
REM Script de inicialização do SmartBling para Windows

echo ===================================
echo SmartBling - Inicializador
echo ===================================
echo.

REM Verificar Python
echo Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python não encontrado. Instale Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python encontrado

REM Verificar Node.js
echo Verificando Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Node.js não encontrado. Instale Node.js 16+
    pause
    exit /b 1
)
echo [OK] Node.js encontrado

REM Backend
echo.
echo Configurando Backend...
cd backend

if not exist "venv" (
    echo Criando ambiente virtual...
    python -m venv venv
)

call venv\Scripts\activate

if not exist ".env" (
    echo Copiando .env.example para .env
    copy .env.example .env
)

echo Instalando dependências...
pip install -q -r requirements.txt

echo [OK] Backend configurado

REM Frontend
echo.
echo Configurando Frontend...
cd ..\frontend

if not exist "node_modules" (
    echo Instalando dependências...
    call npm install -q
)

echo [OK] Frontend configurado

REM Resumo
echo.
echo ===================================
echo [OK] SmartBling pronto para uso!
echo ===================================
echo.
echo Para iniciar:
echo.
echo Terminal 1 - Backend:
echo   cd backend
echo   venv\Scripts\activate
echo   python main.py run
echo.
echo Terminal 2 - Frontend:
echo   cd frontend
echo   npm run dev
echo.
echo Acesse: http://localhost:3000
echo.
echo Para configurar API Bling:
echo   python main.py configurar
echo.
echo OAuth2 (Bling v3) com ngrok:
echo   1^) Inicie o backend: cd backend ^&^& venv\Scripts\activate ^&^& python main.py run
echo   2^) Em outro terminal, inicie o tunel: ngrok http 8000
echo   3^) Copie a URL publica: https://xxxxx.ngrok-free.app
echo   4^) No backend\.env: BLING_REDIRECT_URI=https://xxxxx.ngrok-free.app/callback
echo   5^) Rode: python main.py configurar
echo   6^) Abra o link de autorizacao e COLE o code (ou URL completa) quando solicitado
echo.
pause
