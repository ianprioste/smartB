# 📁 Estrutura do Projeto - smartBling v2

Organização clara e intuitiva do projeto com padrão de clean architecture.

---

## 📂 Estrutura Geral

```
smartBling-v2/                          ← 🌟 Raiz do Projeto
├── README.md                            ← Comece aqui!
├── .gitignore
│
├── doc/                                 ← 📚 Documentação
│   ├── INDEX.md                         ← Mapa de documentação
│   ├── QUICKSTART.md                    ← 5 minutos
│   ├── ARCHITECTURE.md                  ← Arquitetura
│   ├── API.md                           ← Endpoints
│   ├── TESTING.md                       ← Testes
│   ├── DEPLOYMENT.md                    ← Deploy
│   ├── PROJECT_STRUCTURE.md             ← Este arquivo
│   ├── WINDOWS_SETUP.md                 ← Windows
│   └── archive/                         ← Materiais legados
│
├── scripts/                             ← 🔧 Scripts
│   ├── start_server.{bat,sh}
│   ├── start_worker.{bat,sh}
│   └── verify.{bat,sh}
│
└── backend/                             ← 🚀 Código Principal
    ├── run.py                           ← Entry point
    ├── requirements.txt
    ├── .env.example
    ├── docker-compose.yml
    ├── setup.{bat,sh}
    │
    └── app/                             ← 📦 App
        ├── main.py                      ← FastAPI factory
        ├── settings.py                  ← Config
        ├── api/                         ← 🔌 Endpoints
        ├── infra/                       ← 🏗️ Infrastructure
        ├── models/                      ← 📊 ORM + Schemas
        ├── repositories/                ← 🗄️ Data access
        ├── workers/                     ← ⚙️ Celery tasks
        └── domain/                      ← 💼 Business logic
```

---

## 🏗️ Camadas (Clean Architecture)

### 1️⃣ **API** - `app/api/`
**Responsabilidade:** Endpoints HTTP

```python
# app/api/auth.py
POST /auth/bling/connect        # Gera URL OAuth2
GET  /auth/bling/callback       # Callback automático

# app/api/jobs.py
POST   /jobs                    # Criar job
GET    /jobs                    # Listar jobs
GET    /jobs/{id}              # Detalhe job
GET    /jobs/{id}/items        # Items
DELETE /jobs                    # Apagar todos (dev)
```

**Entrada:** HTTP requests (FastAPI)  
**Saída:** HTTP responses (JSON)

---

### 2️⃣ **Services** - `app/services/` *(Sprint 2+)*
**Responsabilidade:** Lógica de negócio

```python
# app/services/job_service.py
class JobService:
    def create_job(db, tenant_id, job_type, payload)
    def process_job(db, job_id)
    # Validações de negócio
```

---

### 3️⃣ **Repositories** - `app/repositories/`
**Responsabilidade:** Acesso a dados

```python
# app/repositories/bling_token_repo.py
class BlingTokenRepository:
    create_or_update()
    get_by_tenant()

# app/repositories/job_repo.py
class JobRepository:
    create()
    get_by_id()
    update_status()
    list_jobs()
```

**Entrada:** Critérios de busca, objetos para persistir  
**Saída:** Entidades do banco

---

### 4️⃣ **Models** - `app/models/`
**Responsabilidade:** Estrutura de dados

#### `database.py` - ORM (SQLAlchemy)
```python
class TenantModel          # Tabela: tenants
class BlingTokenModel      # Tabela: bling_tokens
class JobModel             # Tabela: jobs
class JobItemModel         # Tabela: job_items
```

#### `schemas.py` - Validation (Pydantic)
```python
class JobCreateRequest     # Input validation
class JobResponse          # Output serialization
class BlingAuthUrlResponse
```

---

### 5️⃣ **Infrastructure** - `app/infra/`
**Responsabilidade:** Dependências externas

```python
# app/infra/db.py
- SQLAlchemy engine
- PostgreSQL connection

# app/infra/bling_client.py
- HTTP client (httpx)
- OAuth2 token refresh
- Retry logic
- Structured logging

# app/infra/logging.py
- structlog configuration
- JSON output
- RequestIdMiddleware
```

---

### 6️⃣ **Workers** - `app/workers/`
**Responsabilidade:** Tasks assíncronas

```python
# app/workers/celery_app.py
- Celery configuration
- Windows auto-detection (solo pool)

# app/workers/tasks.py
@celery_app.task
def process_job_task(job_id):
    # Simula processamento
    # Atualiza status
```

**Entrada:** Job ID via fila Redis  
**Saída:** Job atualizado no banco

---

### 7️⃣ **Domain** - `app/domain/` *(Sprint 2+)*
**Responsabilidade:** Lógica de negócio centralizada

```python
# app/domain/entities.py
class Product
class Order

# app/domain/services.py
class ProductService
```

---

## 📊 Fluxo de Dados

### OAuth2 Flow
```
Client
  ↓
POST /auth/bling/connect (api/auth.py)
  ↓
GET /auth/bling/callback (api/auth.py)
  ↓
BlingTokenRepository (repositories/)
  ↓
BlingTokenModel (models/database.py)
  ↓
PostgreSQL
```

### Job Flow
```
Client
  ↓
POST /jobs (api/jobs.py)
  ↓
JobRepository (repositories/)
  ↓
JobModel (models/database.py)
  ↓
PostgreSQL
  ↓
Redis Queue (message broker)
  ↓
Celery Worker (workers/tasks.py)
  ↓
JobRepository (update status)
  ↓
PostgreSQL
```

---

## 🔍 Exemplo: Criar Job

### 1. HTTP Request
```bash
POST /jobs
Content-Type: application/json

{"type":"sync_products","input_payload":{"action":"full"}}
```

### 2. Validação (Pydantic)
```python
# app/models/schemas.py
class JobCreateRequest(BaseModel):
    type: str
    input_payload: Dict
    metadata: Optional[Dict]
```

### 3. Endpoint Handler
```python
# app/api/jobs.py
@router.post("", response_model=JobResponse)
async def create_job(request: JobCreateRequest, db: Session):
    job = JobRepository.create(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        job_type=request.type,
        input_payload=request.input_payload,
    )
    job = JobRepository.update_status(db, job.id, JobStatusEnum.QUEUED)
    return JobResponse.from_orm(job)
```

### 4. Repository
```python
# app/repositories/job_repo.py
@staticmethod
def create(db, tenant_id, job_type, input_payload):
    job = JobModel(
        tenant_id=tenant_id,
        type=job_type,
        status=JobStatusEnum.DRAFT,
        input_payload=input_payload,
    )
    db.add(job)
    db.commit()
    return job
```

### 5. ORM Model
```python
# app/models/database.py
class JobModel(Base):
    __tablename__ = "jobs"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    type: Mapped[str]
    status: Mapped[JobStatusEnum]
    input_payload: Mapped[Dict]
```

### 6. Database
```sql
-- PostgreSQL
INSERT INTO jobs (id, tenant_id, type, status, input_payload, ...)
VALUES (...)
```

### 7. Response
```json
{
  "id": "4d8757e5-...",
  "type": "sync_products",
  "status": "QUEUED",
  "input_payload": {"action": "full"},
  "created_at": "2026-01-22T01:02:07.070706"
}
```

---

## 📁 Arquivos Principais

| Arquivo | Linhas | Propósito |
|---------|--------|----------|
| `app/main.py` | 79 | FastAPI factory |
| `app/api/auth.py` | 167 | OAuth2 endpoints |
| `app/api/jobs.py` | 150+ | Jobs endpoints |
| `app/models/database.py` | 150+ | ORM models |
| `app/models/schemas.py` | 100+ | Pydantic schemas |
| `app/infra/db.py` | 30 | DB connection |
| `app/infra/bling_client.py` | 200+ | Bling client |
| `app/infra/logging.py` | 50+ | Logging config |
| `app/repositories/job_repo.py` | 150+ | Job data access |
| `app/repositories/bling_token_repo.py` | 80+ | Token data access |
| `app/workers/celery_app.py` | 50+ | Celery config |
| `app/workers/tasks.py` | 150+ | Job tasks |

**Total:** ~2500 linhas de código

---

## 🔄 Dependências Entre Módulos

```
API (auth.py, jobs.py)
    ↓
Repositories (job_repo.py, bling_token_repo.py)
    ↓
Models (database.py)
    ↓
Infrastructure (db.py, bling_client.py)

Workers (tasks.py)
    ↓
Repositories
    ↓
Models
    ↓
Infrastructure
```

---

## 🎯 Como Adicionar Feature

### 1. Novo Endpoint
```python
# app/api/novo.py
@router.post("/novo")
async def novo_endpoint(request: NovoRequest, db: Session):
    # Usar repositories
    return NovoResponse
```

### 2. Registrar Router
```python
# app/main.py
from app.api import auth, jobs, novo
app.include_router(novo.router)
```

### 3. Novo Model (se necessário)
```python
# app/models/database.py
class NovoModel(Base):
    pass

# app/models/schemas.py
class NovoRequest(BaseModel):
    pass
```

### 4. Novo Repository
```python
# app/repositories/novo_repo.py
class NovoRepository:
    @staticmethod
    def create(db, **kwargs):
        pass
```

---

## ✅ Checklist de Organização

- [x] Clean architecture implementada
- [x] Separação clara de camadas
- [x] Repositories para data access
- [x] Pydantic para validação
- [x] Celery para async tasks
- [x] Infrastructure isolada
- [x] Logging estruturado
- [x] Documentação de estrutura
- [x] Scripts de inicialização
- [x] Índice de documentação

---

**Status:** ✅ Production-ready (Sprint 1)  
**Última atualização:** 21 Jan 2026

    │   ├── 📁 models/                  # 📊 Data Models
    │   │   ├── __init__.py
    │   │   ├── database.py             # 🗄️ SQLAlchemy ORM
    │   │   │   ├── TenantModel
    │   │   │   ├── BlingTokenModel
    │   │   │   ├── JobModel
    │   │   │   └── JobItemModel
    │   │   └── schemas.py              # 🔀 Pydantic DTOs
    │   │       ├── Auth Schemas
    │   │       ├── Job Schemas
    │   │       └── Health Check
    │   │
    │   ├── 📁 repositories/            # 📚 Data Access Layer
    │   │   ├── __init__.py
    │   │   ├── bling_token_repo.py     # 🔑 Token Management
    │   │   └── job_repo.py             # 📋 Job/Item CRUD
    │   │
    │   └── 📁 workers/                 # 👷 Async Processing
    │       ├── __init__.py
    │       ├── celery_app.py           # ⚙️ Celery Config
    │       └── tasks.py                # 📌 Job Processing Task
    │
    ├── 📁 alembic/                     # 🗄️ Database Migrations
    │   ├── env.py                      # 🔧 Migration Config
    │   ├── script.py.mako              # 📝 Migration Template
    │   ├── alembic.ini
    │   └── 📁 versions/
    │       ├── __init__.py
    │       └── 001_initial_schema.py   # 🎯 Initial Schema
    │           ├── tenants table
    │           ├── bling_tokens table
    │           ├── jobs table
    │           └── job_items table
    │
    └── 📁 tests/                       # 🧪 Tests
        ├── __init__.py
        └── test_integration.py         # ✅ Integration Tests
            ├── test_health_check
            ├── test_oauth_flow
            ├── test_job_creation
            └── test_job_retrieval

═══════════════════════════════════════════════════════════════

📊 ARQUITECTURA EM CAMADAS:

┌─────────────────────────────────────────┐
│         FASTAPI Endpoints               │
│  (auth.py, jobs.py)                    │
├─────────────────────────────────────────┤
│      Services / Use Cases               │
│  (repositories)                         │
├─────────────────────────────────────────┤
│      Models & ORM                       │
│  (database.py, schemas.py)              │
├─────────────────────────────────────────┤
│      Infrastructure Layer               │
│  (db.py, redis.py, logging.py)         │
├─────────────────────────────────────────┤
│      External Services                  │
│  (bling_client.py)                     │
├─────────────────────────────────────────┤
│      Background Jobs                    │
│  (celery, tasks.py)                    │
└─────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════

🗄️ DATABASE SCHEMA:

tenants
  ├─ id (UUID, PK)
  └─ name (String)

bling_tokens
  ├─ id (UUID, PK)
  ├─ tenant_id (FK → tenants)
  ├─ access_token (Text)
  ├─ refresh_token (Text)
  ├─ expires_at (DateTime)
  ├─ token_type (String)
  └─ scope (String)

jobs
  ├─ id (UUID, PK)
  ├─ tenant_id (FK → tenants)
  ├─ type (String)
  ├─ status (DRAFT|QUEUED|RUNNING|DONE|FAILED)
  ├─ input_payload (JSON)
  ├─ metadata (JSON)
  ├─ created_at (DateTime)
  ├─ started_at (DateTime)
  └─ finished_at (DateTime)

job_items
  ├─ id (UUID, PK)
  ├─ job_id (FK → jobs)
  ├─ status (PENDING|RUNNING|OK|ERROR)
  ├─ payload (JSON)
  ├─ result (JSON)
  ├─ error_message (Text)
  ├─ created_at (DateTime)
  ├─ started_at (DateTime)
  └─ finished_at (DateTime)

═══════════════════════════════════════════════════════════════

🔐 FLUXO OAuth2:

1. Cliente chama: POST /auth/bling/connect
2. App retorna: { authorization_url: "https://bling.com.br/oauth..." }
3. Cliente abre URL no navegador
4. Usuário faz login e autoriza no Bling
5. Bling redireciona: GET /auth/bling/callback?code=XXX&state=YYY
6. App troca code por tokens com Bling
7. App salva tokens no BD (encrypted em produção)
8. App retorna: { message: "Connected to Bling successfully" }
9. Tokens são automaticamente renovados quando expiram

═══════════════════════════════════════════════════════════════

📋 FLUXO DE JOBS:

1. Cliente cria job: POST /jobs
   └─ Job status: DRAFT → QUEUED

2. Celery Worker pega job da fila
   └─ Job status: QUEUED → RUNNING
   └─ Cria um JobItem com status: PENDING

3. Worker executa tarefa
   └─ JobItem status: PENDING → RUNNING

4. Tarefa completa
   └─ JobItem status: RUNNING → OK
   └─ Adiciona result ao JobItem

5. Worker finaliza
   └─ Job status: RUNNING → DONE
   └─ Adiciona finished_at ao Job

6. Cliente consulta: GET /jobs/{job_id}
   └─ Vê status DONE

═══════════════════════════════════════════════════════════════

🚀 TECH STACK:

Backend:
  ✅ FastAPI 0.104      - Web Framework
  ✅ Uvicorn 0.24       - ASGI Server
  ✅ SQLAlchemy 2.0     - ORM
  ✅ Psycopg2           - PostgreSQL Driver
  ✅ Pydantic 2.5       - Data Validation
  ✅ Celery 5.3         - Task Queue
  ✅ Redis 5.0          - Message Broker
  ✅ structlog 23.2     - Structured Logging
  ✅ httpx 0.25         - HTTP Client
  ✅ Alembic 1.13       - Migrations

Infrastructure:
  ✅ PostgreSQL 15      - Database
  ✅ Redis 7            - Message Broker
  ✅ Docker             - Containerization

═══════════════════════════════════════════════════════════════

✅ SPRINT 1 COMPLETE

All foundation features implemented and ready for production use.

Next: Sprint 2 - Product Management
