# Deployment Guide

Este projeto foi padronizado para deploy sem Docker.

## Modelo de Deploy

- Backend FastAPI executando diretamente na VPS
- Frontend React/Vite com build estatico servido por Nginx
- Banco de dados configurado por DATABASE_URL (SQLite ou PostgreSQL nativo)
- Redis opcional para filas/cache

## Requisitos da VPS

- Linux (Ubuntu 22.04+ recomendado)
- Python 3.11+
- Node.js 18+
- Nginx
- Git

## Deploy Sem Docker (VPS)

1. Atualizar codigo:

```bash
git pull origin main
```

2. Preparar backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

3. Preparar frontend:

```bash
cd frontend
npm install
npm run build
cd ..
```

4. Configurar ambiente:

- Ajustar backend/.env
- Definir DATABASE_URL
- Definir credenciais BLING_* e SECRET_KEY

5. Rodar backend:

```bash
./.venv/bin/python backend/run.py
```

## Executar como servico (recomendado)

- Use systemd para manter o backend no ar
- Use Nginx como reverse proxy para o backend e para servir o frontend

## Health Check

- API: http://SEU_HOST:8000/health
- Swagger: http://SEU_HOST:8000/docs

## Troubleshooting

- Porta ocupada: finalize processo e reinicie o servico
- Modulo nao encontrado: confirme venv ativa e dependencias instaladas
- Redis indisponivel: backend pode subir sem Redis em desenvolvimento local

## Deploy Automatico via Branch production

Quando houver push na branch `production`, o GitHub Actions executa deploy automatico na VPS.

Workflow:

- Arquivo: `.github/workflows/deploy-main.yml`
- Trigger: push em `production`
- Acao: SSH na VPS, atualiza codigo, instala dependencias, builda frontend e reinicia servicos

### Secrets necessarios no GitHub

Configure em Settings > Secrets and variables > Actions:

- `VPS_HOST` (IP ou dominio da VPS)
- `VPS_USER` (usuario SSH)
- `VPS_SSH_KEY` (chave privada)
- `VPS_PORT` (opcional, default 22)
- `VPS_APP_DIR` (caminho do projeto na VPS, exemplo `/opt/smartB`)
- `VPS_BACKEND_SERVICE` (opcional, default `smartbling-backend`)

### Fluxo recomendado

1. Trabalhar em `dev`.
2. Promover para producao com:

```powershell
./publish.ps1
```

3. O script faz merge `dev -> production` e push.
4. O GitHub Actions inicia deploy automaticamente.
