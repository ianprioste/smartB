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
- Python `venv`/`ensurepip` disponivel (`python3-venv`)
- Node.js 20+
- Nginx (opcional, recomendado para servir o frontend buildado)
- Git
- Usuario SSH com permissao para atualizar o checkout em `/opt/smartB`

## Contrato de Producao

- Branch de deploy: `production`
- Pasta do projeto na VPS: `/opt/smartB`
- Backend em producao: processo sem `reload`, iniciado por `scripts/run-backend-prod.sh`
- Bootstrap de dependencias do sistema: `scripts/bootstrap-vps-deps.sh`
- Deploy remoto idempotente: `scripts/deploy-vps.sh`
- Gerenciamento preferencial do backend: `systemd`
- Health-check esperado: `http://127.0.0.1:8000/health`

## Deploy Sem Docker (VPS)

1. Garantir checkout do projeto:

```bash
git clone https://github.com/ianprioste/smartB.git /opt/smartB
```

2. Bootstrap de dependencias do sistema:

```bash
cd /opt/smartB
bash scripts/bootstrap-vps-deps.sh
```

3. Deploy da branch `production`:

```bash
cd /opt/smartB
APP_DIR=/opt/smartB BACKEND_SERVICE=smartbling-backend bash scripts/deploy-vps.sh
```

4. Configurar ambiente:

- Ajustar backend/.env
- Definir DATABASE_URL
- Definir credenciais BLING_* e SECRET_KEY

5. Rodar backend:

```bash
bash scripts/run-backend-prod.sh
```

## Executar como servico (recomendado)

- Use systemd para manter o backend no ar
- Use Nginx como reverse proxy para o backend e para servir o frontend
- Template de unit file: `deploy/systemd/smartbling-backend.service`

## Health Check

- API: http://SEU_HOST:8000/health
- Swagger: http://SEU_HOST:8000/docs

## Troubleshooting

- Chave SSH invalida: confirme `VPS_SSH_KEY` com a chave privada completa ou base64 valida
- `python3 -m venv` falha: confirme disponibilidade de `python3-venv`
- `.venv` quebrada: o deploy recria automaticamente quando faltar `python` ou `pip`
- Node.js antigo: o bootstrap instala/atualiza para Node.js 20+
- Service inexistente: configure `systemd` com `deploy/systemd/smartbling-backend.service`
- Health-check falhando: verifique logs do backend (`journalctl -u smartbling-backend` ou `/tmp/smartbling-backend.log`)
- Redis indisponivel: backend pode subir sem Redis em desenvolvimento local
- PostgreSQL local indisponivel: o deploy pula Alembic em modo `auto`; para exigir falha em migrations, use `MIGRATIONS_MODE=required`

## Deploy Automatico via Branch production

Quando houver push na branch `production`, o GitHub Actions executa deploy automatico na VPS.

Workflow:

- Arquivo: `.github/workflows/deploy-main.yml`
- Trigger: push em `production`
- Acao: SSH na VPS, sincroniza o checkout em `/opt/smartB`, executa `scripts/deploy-vps.sh`, builda frontend e valida o health-check

### Secrets necessarios no GitHub

Configure em Settings > Secrets and variables > Actions:

- `VPS_HOST` (IP ou dominio da VPS)
- `VPS_USER` (usuario SSH)
- `VPS_SSH_KEY` (chave privada)
- `VPS_PORT` (opcional, default 22)
- `VPS_APP_DIR` (caminho do projeto na VPS, recomendado `/opt/smartB`)
- `VPS_BACKEND_SERVICE` (opcional, default `smartbling-backend`)
- `VPS_FRONTEND_DIR` (opcional, default `/usr/share/nginx/html`)
- `VPS_REPO_URL` (opcional, default `https://github.com/<owner>/<repo>.git`)

### Fluxo recomendado

1. Trabalhar em `dev`.
2. Promover para producao com:

```powershell
./publish.ps1
```

3. Publicar `dev -> production`.
4. O GitHub Actions inicia deploy automaticamente porque o gatilho oficial e sempre push em `production`.
