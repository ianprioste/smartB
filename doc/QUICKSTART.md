# QUICKSTART

Guia rapido para rodar o projeto localmente.

## Pre-requisitos

- Python 3.11+
- Node.js 18+
- npm

## 1) Preparar ambiente

Na raiz do projeto:

Windows PowerShell:

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r backend/requirements.txt
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

## 2) Configurar variaveis de ambiente

Use backend/.env.example como base para backend/.env.

Campos importantes:

- BLING_CLIENT_ID
- BLING_CLIENT_SECRET
- BLING_REDIRECT_URI
- DATABASE_URL
- REDIS_URL

## 3) Rodar backend

Na raiz:

```powershell
./.venv/Scripts/python.exe backend/run.py
```

API disponivel em:

- http://localhost:8000
- http://localhost:8000/docs

## 4) Rodar frontend

Em outro terminal:

```powershell
cd frontend
npm run dev
```

Frontend disponivel em:

- http://localhost:5173

## 5) Validar rapidamente

Backend:

```powershell
curl http://localhost:8000/health
```

Teste principal do backend:

```powershell
cd backend
../.venv/Scripts/python.exe tests/test_events_suite.py
```

## Troubleshooting

- Redis indisponivel: o backend pode iniciar sem Redis em desenvolvimento local, exibindo warning no log.
- Erro de modulo/import: confirme que a .venv esta ativa e que as dependencias foram instaladas.
- Porta 8000 ocupada: finalize o processo em uso da porta e reinicie o backend.
