$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot 'backend'
$frontendPath = Join-Path $repoRoot 'frontend'
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$celeryExe = Join-Path $repoRoot '.venv\Scripts\celery.exe'

function Write-Step($message) {
    Write-Host "[smartB] $message" -ForegroundColor Cyan
}

function Is-Listening($port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

function Ensure-PythonVenv {
    if (Test-Path $venvPython) {
        return
    }

    $pythonInstallerPath = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\python.exe"
    if (-not (Test-Path $pythonInstallerPath)) {
        throw 'Python 3.11 nao encontrado. Instale Python 3.11 e rode novamente.'
    }

    Write-Step 'Criando virtualenv .venv...'
    Push-Location $repoRoot
    try {
        & $pythonInstallerPath -m venv .venv
    } finally {
        Pop-Location
    }
}

function Ensure-BackendReady {
    $envFile = Join-Path $backendPath '.env'
    $envExampleFile = Join-Path $backendPath '.env.example'

    if (-not (Test-Path $envFile) -and (Test-Path $envExampleFile)) {
        Copy-Item $envExampleFile $envFile
        Write-Step 'Arquivo .env criado a partir de .env.example.'
    }

    Write-Step 'Instalando dependencias Python (backend)...'
    Push-Location $backendPath
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $venvPython -m pip install -r requirements.txt 2>&1 | Out-Host
        $pipExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($pipExitCode -ne 0) {
            throw "Falha ao instalar dependencias Python (exit code: $pipExitCode)."
        }

        Write-Step 'Aplicando migrations Alembic...'
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $venvPython -m alembic upgrade head 2>&1 | Out-Host
        $alembicExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($alembicExitCode -ne 0) {
            throw "Falha ao aplicar migrations Alembic (exit code: $alembicExitCode)."
        }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
}

function Ensure-FrontendReady {
    Write-Step 'Instalando dependencias Node (frontend)...'
    Push-Location $frontendPath
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        npm install 2>&1 | Out-Host
        $npmExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        if ($npmExitCode -ne 0) {
            throw "Falha ao instalar dependencias Node (exit code: $npmExitCode)."
        }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
}

function Ensure-BackendRunning {
    if (Is-Listening 8000) {
        Write-Step 'Backend ja esta rodando na porta 8000.'
        return
    }

    Write-Step 'Iniciando backend (FastAPI)...'
    Start-Process -FilePath $venvPython -WorkingDirectory $backendPath -ArgumentList 'run.py' | Out-Null
}

function Ensure-FrontendRunning {
    if (Is-Listening 5173) {
        Write-Step 'Frontend ja esta rodando na porta 5173.'
        return
    }

    Write-Step 'Iniciando frontend (Vite)...'
    Start-Process -FilePath 'npm.cmd' -WorkingDirectory $frontendPath -ArgumentList 'run', 'dev', '--', '--host' | Out-Null
}

function Ensure-WorkerRunning {
    $workerExists = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'celery.exe' -and $_.CommandLine -match 'app.workers.celery_app.celery_app worker' }

    if ($workerExists) {
        Write-Step 'Worker Celery ja esta ativo.'
        return
    }

    Write-Step 'Iniciando worker Celery...'
    Start-Process -FilePath $celeryExe -WorkingDirectory $backendPath -ArgumentList '-A', 'app.workers.celery_app.celery_app', 'worker', '--loglevel=info', '-n', 'worker1@%h' | Out-Null
}

Write-Step 'Preparando stack local...'
Ensure-PythonVenv
Ensure-BackendReady
Ensure-FrontendReady
Ensure-BackendRunning
Ensure-FrontendRunning
Ensure-WorkerRunning

Write-Host ''
Write-Host 'Stack local pronto:' -ForegroundColor Green
Write-Host 'API:      http://localhost:8000/docs'
Write-Host 'Frontend: http://localhost:5173'
Write-Host ''
Write-Host 'Comando usado:' -ForegroundColor DarkGray
Write-Host 'pwsh -ExecutionPolicy Bypass -File .\scripts\start-local.ps1' -ForegroundColor DarkGray
