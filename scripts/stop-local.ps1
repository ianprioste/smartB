$ErrorActionPreference = 'Continue'

$targets = @(
    @{ Name = 'backend'; Pattern = 'run.py' },
    @{ Name = 'frontend'; Pattern = 'vite' },
    @{ Name = 'worker'; Pattern = 'app.workers.celery_app.celery_app worker' }
)

Write-Host '[smartB] Encerrando processos da stack local...' -ForegroundColor Cyan

$allProcesses = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue

foreach ($target in $targets) {
    $matches = $allProcesses | Where-Object {
        ($_.Name -match 'python|node|npm|celery') -and ($_.CommandLine -match [Regex]::Escape($target.Pattern))
    }

    foreach ($process in $matches) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "[smartB] Parado: $($target.Name) (PID $($process.ProcessId))"
    }
}

Write-Host '[smartB] Processos finalizados (quando encontrados).' -ForegroundColor Green
