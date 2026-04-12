#!/usr/bin/env pwsh
<#
Quick diagnostic for excessive API calls issue.

This script:
1. Starts the backend in background
2. Runs the diagnostic
3. Shows results

Usage: .\diagnose.ps1
#>

Write-Host "`n" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🔍 Diagnostic: Excessive API Calls" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "`n"

# Check if backend is already running
Write-Host "📋 Checking backend status..."

try {
    $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
    Write-Host "✅ Backend already running" -ForegroundColor Green
    $need_backend = $false
} catch {
    Write-Host "⚠️  Backend not running, starting..." -ForegroundColor Yellow
    $need_backend = $true
}

# Start backend if needed
if ($need_backend) {
    Write-Host "   Starting: python backend\run.py"
    Start-Process -FilePath "$PSScriptRoot\.\.venv\Scripts\python.exe" `
                  -ArgumentList "$PSScriptRoot\backend\run.py" `
                  -WorkingDirectory $PSScriptRoot `
                  -WindowStyle Hidden `
                  -PassThru | Out-Null
    
    Write-Host "   Waiting for backend to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    
    # Verify
    $max_retries = 10
    $retry = 0
    while ($retry -lt $max_retries) {
        try {
            $health = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
            Write-Host "✅ Backend started successfully" -ForegroundColor Green
            break
        } catch {
            $retry++
            if ($retry -lt $max_retries) {
                Start-Sleep -Seconds 1
            }
        }
    }
    
    if ($retry -eq $max_retries) {
        Write-Host "❌ Failed to start backend" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n"

# Run diagnostic
Write-Host "🔄 Running diagnostic..." -ForegroundColor Cyan
Write-Host "`n"

push-location (Join-Path $PSScriptRoot "backend")
    & "$PSScriptRoot\.\.venv\Scripts\python.exe" diagnose_requests.py
pop-location

Write-Host "`n"
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "✅ Diagnostic complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "`n"
Write-Host "📖 For detailed explanation, see:" -ForegroundColor Yellow
Write-Host "   $PSScriptRoot\ACTION_PLAN_EXCESSIVE_REQUESTS.md" -ForegroundColor Cyan
Write-Host "   $PSScriptRoot\DIAGNOSTIC_EXCESSIVE_REQUESTS.md" -ForegroundColor Cyan
Write-Host "`n"

Read-Host "Press Enter to exit"
