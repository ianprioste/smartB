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
