# smartBling v2 - Sprint 1 🚀

Backend SaaS integrado com Bling ERP (API v3). Sprint 1 entrega base funcional com OAuth2, Job infrastructure e observabilidade estruturada.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Quick Start (5 min)](#quick-start-5-min)
- [Arquitetura](#arquitetura)
- [Endpoints](#endpoints)
- [Configuração](#configuração)
- [Troubleshooting](#troubleshooting)

---

## Visão Geral

| Item | Status |
|------|--------|
| **OAuth2 Bling** | ✅ Implementado |
| **BlingClient** | ✅ Retry automático + Logging |
| **Jobs** | ✅ API + DB + Worker |
| **Logging** | ✅ JSON estruturado |
| **Database** | ✅ PostgreSQL + Alembic |
| **Queue** | ✅ Redis + Celery |
| **Documentação** | ✅ API + Exemplos |

---

## Quick Start (5 min)

### Pré-requisitos
- Python 3.11+
- Docker & Docker Compose
- Git

### Passos

**1. Clone e configure:**
```bash
cd backend
cp .env.example .env
```

**2. Edite `.env` com credenciais Bling:**
```bash
BLING_CLIENT_ID=seu_id_aqui
BLING_CLIENT_SECRET=seu_secret_aqui
```

**3. Inicie serviços (PostgreSQL + Redis):**
```bash
docker-compose up -d
```

**4. Instale dependências:**
```bash
pip install -r requirements.txt
```

**5. Inicie server (Terminal 1):**
```bash
python run.py
```
Acesse: http://localhost:8000/docs

**6. Inicie worker (Terminal 2):**
```bash
# Windows
python celery_worker_windows.py

# Linux/Mac
celery -A app.workers.celery_app worker --loglevel=info
```

---

## Arquitetura

```
backend/
├── app/
│   ├── main.py                 # FastAPI app factory
│   ├── settings.py             # .env configuration
│   ├── run.py                  # Entry point
│   ├── api/
│   │   ├── auth.py            # OAuth2 endpoints
│   │   └── jobs.py            # Job management
│   ├── domain/                 # Business logic (Sprint 2+)
│   ├── infra/
│   │   ├── db.py              # SQLAlchemy + PostgreSQL
│   │   ├── bling_client.py    # Bling API client
│   │   └── logging.py         # Structured logging
│   ├── models/
│   │   ├── database.py        # ORM models
│   │   └── schemas.py         # Pydantic validators
│   ├── repositories/
│   │   ├── bling_token_repo.py
│   │   └── job_repo.py
│   └── workers/
│       ├── celery_app.py      # Celery config (auto solo on Windows)
│       └── tasks.py           # Async tasks
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── alembic/                    # DB migrations
```

**Padrão:** 7-layer clean architecture (API → Domain → Infra → Models → Repos → Workers → Tests)

---

## Endpoints

### Auth (OAuth2)

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/auth/bling/connect` | Gera URL de autorização do Bling |
| `GET` | `/auth/bling/callback` | Callback do Bling (automático) |

### Jobs

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/jobs` | Cria novo job |
| `GET` | `/jobs` | Lista jobs recentes |
| `GET` | `/jobs/{id}` | Obtém job por ID |
| `GET` | `/jobs/{id}/detail` | Job + items |
| `GET` | `/jobs/{id}/items` | Items do job |
| `DELETE` | `/jobs` | ⚠️ Apaga todos (dev only) |

### Health

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Status da app |

---

## Configuração

### Arquivo `.env`

```bash
# Bling OAuth2
BLING_CLIENT_ID=seu_client_id
BLING_CLIENT_SECRET=seu_client_secret
BLING_REDIRECT_URI=http://localhost:8000/auth/bling/callback

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smartbling

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Logging
LOG_LEVEL=INFO
DEBUG=False
```

### Bling Setup

1. Acesse: https://www.bling.com.br/oauth/applications
2. Registre seu app
3. Configure redirect URI: `http://localhost:8000/auth/bling/callback`
4. Copie `Client ID` e `Client Secret` para `.env`

---

## Troubleshooting

### "Connection refused" - Redis/PostgreSQL

```bash
docker-compose ps
docker-compose logs postgres
docker-compose logs redis
```

### "Port 8000 already in use"

```bash
# Linux/Mac
lsof -i :8000 && kill -9 <PID>

# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Worker não processa jobs

```bash
# Check celery tasks
celery -A app.workers.celery_app inspect active

# Debug mode
celery -A app.workers.celery_app worker --loglevel=debug
```

### OAuth erro "invalid_client"

- ✅ Verificar BLING_CLIENT_ID e BLING_CLIENT_SECRET no `.env`
- ✅ Verificar Redirect URI registrada no Bling
- ✅ Confirmar que o token não expirou

---

## Documentação Complementar

- [QUICKSTART.md](QUICKSTART.md) - Guia visual passo-a-passo
- [DEVELOPMENT.md](DEVELOPMENT.md) - Arquitetura e decisões técnicas
- [EXAMPLES.md](EXAMPLES.md) - Exemplos de uso dos endpoints
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Detalhes do projeto
- [SPRINT1_SUMMARY.md](SPRINT1_SUMMARY.md) - Resumo do Sprint 1

---

## Scripts

Scripts de inicialização estão em `/scripts`:
- `start_server.bat` / `start_server.sh` - Inicia FastAPI
- `start_worker.bat` / `start_worker.sh` - Inicia Celery worker
- `verify.bat` / `verify.sh` - Verifica dependências

---

## Próximas Sprints

- [ ] Autenticação JWT para API
- [ ] Endpoints de Produtos (CRUD via Bling)
- [ ] Endpoints de Pedidos
- [ ] Health checks avançados
- [ ] Rate limiting
- [ ] Testes com 80%+ coverage

---

## Recursos

- [Bling API Docs](https://developers.bling.com.br/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Celery Docs](https://docs.celeryproject.io/)


## 🔐 OAuth2 - Fluxo de Autenticação

### 1. Obtenha a URL de Autorização

```bash
curl -X POST http://localhost:8000/auth/bling/connect
```

Resposta:
```json
{
  "authorization_url": "https://bling.com.br/oauth/authorize?client_id=...&state=..."
}
```

### 2. Redirecione o Usuário

O usuário clica no link e autoriza a aplicação no Bling.

### 3. Callback Automático

Bling redireciona para:
```
http://localhost:8000/auth/bling/callback?code=XXX&state=YYY
```

Os tokens são automaticamente salvos no banco de dados.

## 📋 API - Jobs

### Criar um Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "sync_products",
    "input_payload": {"action": "full_sync"},
    "metadata": {"source": "manual"}
  }'
```

Resposta:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "sync_products",
  "status": "QUEUED",
  "created_at": "2024-01-21T10:00:00",
  "started_at": null,
  "finished_at": null
}
```

### Consultar Status do Job

```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000
```

### Ver Detalhes Completos (com items)

```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/detail
```

### Listar Items do Job

```bash
curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/items
```

## 📊 BlingClient - Exemplo de Uso

```python
from app.infra.bling_client import BlingClient
from datetime import datetime

client = BlingClient(
    access_token="seu_token_aqui",
    refresh_token="seu_refresh_token",
    token_expires_at=datetime.utcnow() + timedelta(hours=1)
)

# GET request
products = await client.get("/products")

# POST request
product = await client.post("/products", {
    "name": "Product Name",
    "price": 100.00
})

client.close()
```

**Recursos:**
- ✅ Token refresh automático
- ✅ Retry com backoff exponencial
- ✅ Logs estruturados
- ✅ Suporta 429 (rate limit) e 5xx

## 🛠️ Estrutura de Dados

### Jobs Table

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | UUID | Identificador único |
| tenant_id | UUID | Tenant da aplicação |
| type | String | Tipo de job (ex: sync_products) |
| status | Enum | DRAFT, QUEUED, RUNNING, DONE, FAILED |
| input_payload | JSON | Configuração do job |
| metadata | JSON | Metadados adicionais |
| created_at | DateTime | Criação |
| started_at | DateTime | Início da execução |
| finished_at | DateTime | Finalização |

### Job Items Table

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | UUID | Identificador único |
| job_id | UUID | Referência ao job |
| status | Enum | PENDING, RUNNING, OK, ERROR |
| payload | JSON | Dados do item |
| result | JSON | Resultado da execução |
| error_message | Text | Mensagem de erro (se houver) |

### Bling Tokens Table

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | UUID | Identificador único |
| tenant_id | UUID | Tenant |
| access_token | Text | OAuth2 access token |
| refresh_token | Text | OAuth2 refresh token |
| expires_at | DateTime | Expiração do token |
| token_type | String | Tipo (Bearer) |
| scope | String | Escopos autorizados |

## 📝 Logging Estruturado

Todos os logs são em formato JSON com estrutura:

```json
{
  "timestamp": "2024-01-21T10:00:00.000Z",
  "level": "INFO",
  "logger": "app.api.jobs",
  "message": "job_created_and_queued",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Eventos principais:**
- `job_created_and_queued` - Job criado
- `job_processing_started` - Worker iniciou
- `job_processing_completed` - Job completo
- `api_request` - Requisição à API Bling
- `token_refresh_success` - Token renovado
- `oauth_callback_received` - OAuth2 callback recebido

## 🚨 Troubleshooting

### Erro: "connection refused" no Redis

```bash
# Verifique se o container está rodando
docker-compose ps

# Restart
docker-compose restart redis
```

### Erro: "permission denied" no PostgreSQL

```bash
# Verifique permissões
docker-compose logs postgres

# Se necessário, remova e recrie
docker-compose down -v
docker-compose up -d
```

### Worker não processa jobs

```bash
# Verifique se o worker está rodando
celery -A app.workers.celery_app inspect active

# Veja os logs
celery -A app.workers.celery_app worker --loglevel=debug
```

## 🔒 Segurança (Production)

**TODO para produção:**
- ❌ Encriptar access_token e refresh_token no DB
- ❌ Usar HTTPS
- ❌ Validar CSRF state com session segura
- ❌ Rate limiting em endpoints
- ❌ Autenticação em endpoints de jobs
- ❌ Configurar CORS adequadamente

## 📚 Next Steps (Sprint 2+)

- [ ] Cadastro de produtos
- [ ] Sincronização de inventário
- [ ] Composição de produtos
- [ ] Upload de arquivos
- [ ] Dashboard UI
- [ ] Webhooks do Bling
- [ ] Testes automatizados

---

**Última atualização:** 21/01/2025
