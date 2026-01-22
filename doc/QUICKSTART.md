# 🚀 QUICKSTART - 5 Minutos para Começar

## ⚡ Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- PowerShell (Windows) ou Bash (Linux/Mac)

---

## 1️⃣ Clone e Configure

```bash
cd backend
cp .env.example .env
```

Edite `.env` com suas credenciais:
```ini
BLING_CLIENT_ID=seu_client_id
BLING_CLIENT_SECRET=seu_client_secret
```

## 2️⃣ Inicie Serviços (PostgreSQL + Redis)

```bash
docker-compose up -d
```

Aguarde ~30s. Verifique com:
```bash
docker-compose ps
```

## 3️⃣ Instale Dependências

```bash
pip install -r requirements.txt
```

## 4️⃣ Inicie o Servidor

**Terminal 1:**
```bash
cd backend
python run.py
```

✅ Acesse: http://localhost:8000/docs (Swagger UI)

## 5️⃣ Inicie o Worker

**Terminal 2:**
```bash
cd backend

# Windows
python celery_worker_windows.py

# Linux/Mac
celery -A app.workers.celery_app worker --loglevel=info
```

---

## 🔐 OAuth2 - Conectar ao Bling

### Opção 1: Swagger UI (Recomendado)

1. Abra http://localhost:8000/docs
2. Expanda "auth" → "POST /auth/bling/connect"
3. Clique "Try it out" → "Execute"
4. Copie o `authorization_url`
5. Abra em novo aba
6. Autorize no Bling
7. Será redirecionado e tokens salvos! ✅

### Opção 2: cURL

```bash
curl -X POST http://localhost:8000/auth/bling/connect
```

Cole o `authorization_url` retornado no navegador.

---

## 📋 Criar um Job

```bash
curl -X POST http://localhost:8000/jobs ^
  -H "Content-Type: application/json" ^
  -d "{\"type\":\"sync_products\",\"input_payload\":{\"action\":\"full_sync\"},\"metadata\":{\"source\":\"quickstart\"}}"
```

**Resposta:**
```json
{
  "id": "4d8757e5-f204-4c62-96f0-73ca89815035",
  "type": "sync_products",
  "status": "QUEUED",
  "input_payload": {"action": "full_sync"},
  "job_metadata": {"source": "quickstart"},
  "created_at": "2026-01-22T01:02:07.070706"
}
```

## 📊 Monitorar Job

```bash
# Listar todos os jobs
curl http://localhost:8000/jobs

# Ver job específico
curl http://localhost:8000/jobs/4d8757e5-f204-4c62-96f0-73ca89815035

# Ver detalhes + items
curl http://localhost:8000/jobs/4d8757e5-f204-4c62-96f0-73ca89815035/detail

# Ver items do job
curl http://localhost:8000/jobs/4d8757e5-f204-4c62-96f0-73ca89815035/items
```

Observe o status mudar: `QUEUED` → `RUNNING` → `DONE`

---

## 🆘 Problemas Comuns

### ❌ "Port 8000 already in use"

```bash
# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000 && kill -9 <PID>
```

### ❌ "Connection refused" (Redis/PostgreSQL)

```bash
docker-compose ps
docker-compose logs postgres
```

### ❌ OAuth erro 404 na URL

- Verifique BLING_CLIENT_ID, BLING_CLIENT_SECRET no `.env`
- Registre Redirect URI no Bling: `http://localhost:8000/auth/bling/callback`

### ❌ Worker não processa jobs

```bash
# Ver tasks ativas
celery -A app.workers.celery_app inspect active

# Debug detalhado
celery -A app.workers.celery_app worker --loglevel=debug
```

---

## 📚 Documentação Completa

- [README.md](README.md) - Visão geral completa
- [DEVELOPMENT.md](DEVELOPMENT.md) - Arquitetura detalhada
- [EXAMPLES.md](EXAMPLES.md) - Exemplos de uso
- [CODE_REVIEW.md](../CODE_REVIEW.md) - Análise de código

---

## ✅ Checklist de Setup

- [ ] `.env` configurado com credenciais Bling
- [ ] Docker containers rodando: `docker-compose ps`
- [ ] Server iniciado: `python run.py`
- [ ] Worker iniciado: `python celery_worker_windows.py`
- [ ] Swagger acessível: http://localhost:8000/docs
- [ ] OAuth conectado ao Bling
- [ ] Job criado e processado com sucesso


```bash
# Create job
JOB=$(curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "sync_products",
    "input_payload": {"action": "full_sync"},
    "metadata": {"source": "quickstart"}
  }')

JOB_ID=$(echo $JOB | jq -r '.id')
echo "Job ID: $JOB_ID"

# Check status
curl http://localhost:8000/jobs/$JOB_ID

# Wait a few seconds for worker to process...
sleep 3

# Check again
curl http://localhost:8000/jobs/$JOB_ID

# See job items
curl http://localhost:8000/jobs/$JOB_ID/items

# Full details
curl http://localhost:8000/jobs/$JOB_ID/detail
```

### Via Swagger UI

1. http://localhost:8000/docs
2. Expanda "jobs"
3. POST /jobs → "Try it out"
4. Cole o payload:
```json
{
  "type": "sync_products",
  "input_payload": {"action": "full_sync"},
  "metadata": {"source": "quickstart"}
}
```
5. Execute
6. Copie o `id`
7. GET /jobs/{job_id} com o ID
8. Execute várias vezes para ver status mudar

## 🔍 Ver Logs

```bash
# FastAPI logs
tail -f logs/app.log

# Celery worker logs
# Verá no terminal do worker

# Check database
docker exec -it smartbling-postgres-1 psql -U postgres -d smartbling -c "SELECT * FROM jobs;"
```

## 🧪 Testar Tudo

```bash
# Run integration tests (requer test DB)
pytest tests/test_integration.py -v
```

## 📊 Status da Arquitetura

| Componente | Status | Detalhes |
|-----------|--------|----------|
| ✅ FastAPI | Ready | Endpoints funcionando |
| ✅ PostgreSQL | Ready | Tabelas criadas |
| ✅ Redis | Ready | Cache pronto |
| ✅ OAuth2 | Ready | Bling integration OK |
| ✅ BlingClient | Ready | Retry + logging |
| ✅ Jobs | Ready | DB + API + Worker |
| ✅ Logging | Ready | JSON estruturado |
| ❌ Auth (JWT) | Not in Sprint 1 | |
| ❌ Produtos | Not in Sprint 1 | |

## 🆘 Troubleshooting

### "Connection refused" - Redis/PostgreSQL

```bash
docker-compose ps
docker-compose logs postgres
docker-compose logs redis
```

### "Port 8000 already in use"

```bash
# Linux/Mac
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Worker não processa jobs

```bash
# Check celery tasks
celery -A app.workers.celery_app inspect active

# Check celery logs
celery -A app.workers.celery_app worker --loglevel=debug
```

### "Database does not exist"

```bash
docker exec -it smartbling-postgres-1 psql -U postgres -c "CREATE DATABASE smartbling;"
python run.py  # Vai criar as tabelas
```

## 🎯 Próximos Passos

Depois do setup, você pode:

1. **Explorar Swagger UI**: http://localhost:8000/docs
2. **Ler README.md**: Documentação completa
3. **Ler DEVELOPMENT.md**: Arquitetura e decisões
4. **Ver EXAMPLES.md**: Exemplos de uso
5. **Modificar `app/workers/tasks.py`**: Adicionar lógica real de jobs
6. **Criar novos endpoints**: Em `app/api/`

## 📚 Recursos

- [Bling API Docs](https://developers.bling.com.br/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Celery Docs](https://docs.celeryproject.io/)

## 💡 Dicas

- Use `docker-compose logs -f` para ver logs em tempo real
- Altere `LOG_LEVEL` em `.env` para `DEBUG` para mais verbosidade
- Tokens OAuth2 são salvos no banco (mascarados em logs)
- Jobs são processados automaticamente pelo worker
- Cada request tem um `request_id` único nos logs

---

**Última atualização:** 21/01/2025  
**Versão:** 0.1.0  
**Sprint:** 1 - Foundation
