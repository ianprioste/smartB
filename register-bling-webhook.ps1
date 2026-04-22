#!/usr/bin/env pwsh
<#
.SYNOPSIS
Register and manage Bling webhooks for order status updates.

.DESCRIPTION
This script helps you:
1. List existing webhooks in Bling
2. Register a new webhook for order updates
3. Test the webhook integration

.PARAMETER Command
The command to execute: list, register, or test

.PARAMETER BackendUrl
The backend URL (default: http://localhost:8000)

.EXAMPLE
./register-bling-webhook.ps1 -Command list
./register-bling-webhook.ps1 -Command register
./register-bling-webhook.ps1 -Command test -BackendUrl http://localhost:8000
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list", "register", "test")]
    [string]$Command,
    
    [string]$BackendUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Text)
    Write-Host "`n================================" -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "================================`n" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "OK: $Text" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Text)
    Write-Host "ERRO: $Text" -ForegroundColor Red
}

function Invoke-ApiCall {
    param(
        [string]$Method,
        [string]$Url,
        [object]$Body = $null
    )
    
    try {
        $params = @{
            Uri = $Url
            Method = $Method
            UseBasicParsing = $true
            TimeoutSec = 30
        }
        
        if ($Body) {
            $params["ContentType"] = "application/json"
            $params["Body"] = $Body | ConvertTo-Json -Compress -Depth 10
        }
        
        $response = Invoke-WebRequest @params
        return @{
            StatusCode = [int]$response.StatusCode
            Content = $response.Content | ConvertFrom-Json
        }
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
            $body = $reader.ReadToEnd()
            $reader.Dispose()
            
            return @{
                StatusCode = [int]$resp.StatusCode
                Content = if ($body) { try { ConvertFrom-Json $body } catch { $body } } else { $null }
                Error = $true
            }
        } else {
            throw $_
        }
    }
}

# Main execution
switch ($Command) {
    "list" {
        Write-Header "Listando Webhooks do Bling"
        
        Write-Host "Buscando webhooks..." -ForegroundColor Yellow
        $result = Invoke-ApiCall -Method "GET" -Url "$BackendUrl/webhooks/bling/list-webhooks"
        
        if ($result.StatusCode -eq 200) {
            Write-Success "Webhooks obtidos com sucesso"
            
            $webhooks = $result.Content.webhooks
            if ($webhooks.Count -eq 0) {
                Write-Host "Nenhum webhook registrado." -ForegroundColor Yellow
            } else {
                Write-Host "`nWebhooks registrados:" -ForegroundColor Cyan
                $webhooks | ForEach-Object {
                    Write-Host "  - ID: $($_.id)" -ForegroundColor White
                    Write-Host "    Nome: $($_.nome)" -ForegroundColor White
                    Write-Host "    URL: $($_.url)" -ForegroundColor White
                    Write-Host "    Eventos: $($_.eventos -join ', ')" -ForegroundColor White
                    Write-Host ""
                }
            }
        } else {
            Write-Fail "Falha ao listar webhooks (HTTP $($result.StatusCode))"
            if ($result.Content) {
                Write-Host ($result.Content | ConvertTo-Json -Depth 5) -ForegroundColor Red
            }
            exit 1
        }
    }
    
    "register" {
        Write-Header "Registrando Webhook no Bling"
        
        Write-Host "Isso vai registrar um webhook para que quando um pedido mude de status no Bling,"
        Write-Host "a atualizacao seja enviada para seu app e refletida imediatamente.`n" -ForegroundColor Yellow
        
        Write-Host "Enviando requisicao de registro..." -ForegroundColor Yellow
        $result = Invoke-ApiCall -Method "POST" -Url "$BackendUrl/webhooks/bling/register-order-webhook"
        
        if ($result.StatusCode -eq 200) {
            Write-Success "Webhook registrado com sucesso!"
            Write-Host "`nDetalhes:" -ForegroundColor Cyan
            Write-Host "  URL: $($result.Content.webhook_url)" -ForegroundColor White
            Write-Host "  Status: Ativo" -ForegroundColor Green
            Write-Host "`nSeu app vai receber atualizacoes do Bling sempre que o status mudar.`n" -ForegroundColor Cyan
        } else {
            Write-Fail "Falha ao registrar webhook (HTTP $($result.StatusCode))"
            if ($result.Content -and $result.Content.detail) {
                Write-Host "Erro: $($result.Content.detail)" -ForegroundColor Red
            }
            exit 1
        }
    }
    
    "test" {
        Write-Header "Testando Endpoint de Webhook"
        
        Write-Host "Enviando payload de teste para seu app..." -ForegroundColor Yellow
        
        $testPayload = @{
            data = @{
                id = 1128
                numero = "1128"
                situacao = @{
                    id = 6
                    nome = "Em aberto"
                }
                totalVenda = 100.00
            }
            event = "pedido.atualizado"
        } | ConvertTo-Json
        
        try {
            $response = Invoke-WebRequest -Uri "$BackendUrl/webhooks/bling/orders" `
                -Method POST `
                -ContentType "application/json" `
                -Body $testPayload `
                -UseBasicParsing `
                -TimeoutSec 10
            
            if ([int]$response.StatusCode -eq 202) {
                Write-Success "Teste de webhook bem-sucedido (HTTP 202 - Aceito)"
                Write-Host "`nSeu endpoint de webhook esta funcionando corretamente!" -ForegroundColor Green
            } else {
                Write-Fail "Codigo de resposta inesperado: HTTP $([int]$response.StatusCode)"
            }
        } catch {
            Write-Fail "Falha ao enviar webhook de teste: $($_.Exception.Message)"
            exit 1
        }
    }
}

Write-Host ""
