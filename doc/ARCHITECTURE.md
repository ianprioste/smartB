# 🏗️ Arquitetura - smartBling v2

## 📊 Visão Geral

smartBling v2 é um SaaS que integra dados de impressoras digitais com Bling ERP, automatizando criação e sincronização de produtos.

```
┌─────────────────────────────────────────────────────────────┐
│                      Usuário Final (Browser)                │
└─────────────────────────────────────────────────────────────┘
              ↓                            ↓
┌──────────────────────────────┐  ┌────────────────────────┐
│   Frontend (React + Vite)    │  │   Admin Panel (UI)     │
│  - Wizard (Create Plans)     │  │  - Models/Colors CRUD  │
│  - Real-time Updates        │  │  - Template Lookup     │
│  - Form Validation          │  │  - Status Monitoring   │
└──────────────────────────────┘  └────────────────────────┘
              ↓                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (8000)                  │
├─────────────────────────────────────────────────────────────┤
│ API Layer          Domain Layer         Infra Layer        │
│                                                              │
│ ├─ /auth            ├─ Entities        ├─ BlingClient    │
│ ├─ /admin          ├─ Value Objects   ├─ PostgreSQL     │
│ ├─ /plans          ├─ Use Cases       ├─ Redis          │
│ ├─ /config         └─ Business Logic  └─ Logging        │
│ └─ /webhooks                                              │
│                                                              │
│ Repositories → Data Access (Tenant-Isolated)              │
│ Services → Business Logic & Orchestration                │
│ Workers → Celery Tasks (Async)                          │
└─────────────────────────────────────────────────────────────┘
              ↓                   ↓              ↓
     ┌────────────────┐   ┌──────────────┐  ┌──────────────┐
     │  PostgreSQL    │   │    Redis     │  │ Bling API    │
     │                │   │              │  │              │
     │ - Users        │   │ - Cache      │  │ - OAuth      │
     │ - Models       │   │ - Sessions   │  │ - Products   │
     │ - Colors       │   │ - Queues     │  │ - Sync       │
     │ - Templates    │   │              │  │              │
     │ - Plans        │   └──────────────┘  └──────────────┘
     │ - Jobs         │
     └────────────────┘
```

---

## 📁 Estrutura de Código

### Backend

```
backend/
├── app/
│   ├── main.py                    # FastAPI app initialization
│   ├── settings.py                # Configuration & env vars
│   ├── constants.py              # 🆕 Centralized constants
│   │
│   ├── api/                       # API Layer (Routes & Handlers)
│   │   ├── auth.py               # OAuth2 flow
│   │   ├── admin.py              # Models, Colors, Templates
│   │   ├── plans.py              # Plan creation & execution
│   │   ├── wizard_new.py         # Wizard flow
│   │   ├── config.py             # Configuration endpoints
│   │   ├── product_plan.py       # Plan execution details
│   │   └── plan_execution.py     # ✅ Refactored execution logic
│   │
│   ├── domain/                    # Domain Layer (Business Logic)
│   │   ├── entities/             # Domain entities
│   │   │   ├── plan.py           # Plan entity
│   │   │   ├── product.py        # Product entity
│   │   │   └── template.py       # Template entity
│   │   │
│   │   ├── value_objects/        # Value objects (Color, Size, etc)
│   │   │
│   │   └── services/             # Business logic
│   │       ├── plan_service.py   # Plan orchestration
│   │       ├── bling_service.py  # Bling integration
│   │       └── template_service.py
│   │
│   ├── models/                    # Data Models Layer
│   │   ├── database.py            # SQLAlchemy ORM models
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── enums.py               # Enums (TemplateKind, etc)
│   │
│   ├── repositories/              # Data Access Layer
│   │   ├── base.py               # 🆕 Base repository with common CRUD
│   │   ├── model_repo.py         # ✅ Refactored with BaseRepository
│   │   ├── color_repo.py         # ✅ Refactored with BaseRepository
│   │   ├── model_template_repo.py # ✅ Refactored with BaseRepository
│   │   ├── job_repo.py           # Job tracking
│   │   ├── plan_repo.py          # Plan persistence
│   │   └── bling_token_repo.py   # OAuth token storage
│   │
│   ├── infra/                     # Infrastructure Layer
│   │   ├── db.py                 # Database connection & session
│   │   ├── bling_client.py       # Bling API client
│   │   ├── logging.py            # JSON logging setup
│   │   ├── cache.py              # Redis cache helpers
│   │   └── security.py           # Auth & token handling
│   │
│   ├── workers/                   # Celery Tasks
│   │   ├── plan_executor.py      # Execute plans async
│   │   ├── sync_products.py      # Sync with Bling
│   │   └── cleanup_tasks.py      # Maintenance tasks
│   │
│   └── __init__.py
│
├── tests/                         # 🆕 Test structure
│   ├── conftest.py               # Pytest fixtures
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   └── e2e/                       # End-to-end tests
│
├── alembic/                       # Database migrations
│   └── versions/                  # Migration scripts
│
├── run.py                         # Server entry point
├── celery_worker.py              # Worker entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── docker-compose.yml            # Development containers
```

### Frontend

```
frontend/
├── src/
│   ├── main.jsx                   # React entry point
│   ├── App.jsx                    # App root component
│   │
│   ├── pages/
│   │   ├── admin/                # Admin panel
│   │   │   ├── AdminPages.jsx    # 🆕 Split into components
│   │   │   └── components/       # Child components
│   │   │
│   │   └── wizard/               # Wizard flow
│   │       ├── WizardNew.jsx     # 🆕 Split into steps
│   │       └── components/       # Step components
│   │
│   ├── components/               # Reusable components
│   │   ├── Header.jsx
│   │   ├── Footer.jsx
│   │   ├── Table.jsx
│   │   └── Modal.jsx
│   │
│   ├── hooks/                    # 🆕 Custom React hooks
│   │   ├── useAdmin.js          # Admin state management
│   │   ├── useWizard.js         # Wizard state management
│   │   └── useApi.js            # API calls
│   │
│   ├── services/                 # API service layer
│   │   ├── api.js               # Axios instance
│   │   ├── auth.js              # Auth API calls
│   │   └── plans.js             # Plan API calls
│   │
│   ├── styles/                   # 🆕 Organized CSS
│   │   ├── index.css            # Global styles
│   │   ├── components/          # Component styles
│   │   └── pages/               # Page styles
│   │
│   └── utils/                    # Utility functions
│       ├── formatters.js
│       ├── validators.js
│       └── constants.js
│
└── public/                        # Static assets
    └── logo.svg
```

---

## 🔄 Fluxo de Dados

### 1. Criar Plano (Wizard)

```
Usuario (Frontend)
     ↓
[Wizard Form Steps]
├─ Step 1: Print Specs
├─ Step 2: Select Models
├─ Step 3: Select Colors
├─ Step 4: Template Search
└─ Step 5: Review & Submit
     ↓
POST /plans/create
     ↓
PlanService.create_plan()
├─ Validate input
├─ Build plan structure
├─ Store in DB (PENDING)
└─ Enqueue execution
     ↓
Response: Plan ID + Status
     ↓
WebSocket: Real-time updates
```

### 2. Executar Plano

```
execute_plan_direct(plan_json)
     ↓
[STEP 1] Create Bases
├─ Collect all SKUs
├─ Bulk check in Bling (single GET)
├─ Create BASE_PARENT with variations
└─ Store base_ids in cache
     ↓
[STEP 2] Create Produtos
├─ Build variations with composition
├─ Create PARENT_PRINTED with format E variations
└─ Store parent_ids in cache
     ↓
[STEP 3] Update Produtos
├─ Fetch existing products
├─ Merge variations
├─ Add composition (estructura)
└─ PUT updated product
     ↓
[Result]
└─ Return execution summary
     ↓
Celery: Async follow-up tasks
```

### 3. Sincronizar com Bling

```
BlingClient.get_products()
     ↓
[Batch requests]
├─ codigos[] (SKUs)
├─ tipo=T (product type)
└─ limite=100
     ↓
[Cache results in Redis]
└─ 5 min TTL
     ↓
[Use in execution]
└─ get_id_from_cache(sku)
```

---

## 🏛️ Padrões de Design

### 1. Repository Pattern
Acesso a dados centralizado e testável.

```python
# Antes (duplicação)
@staticmethod
def get_by_id(db: Session, tenant_id: UUID, id: UUID):
    return db.query(ModelModel).filter(...).first()

# Depois (BaseRepository)
class ModelRepository(BaseRepository[ModelModel]):
    model_class = ModelModel
    
    @classmethod
    def get_by_code(cls, db: Session, tenant_id: UUID, code: str):
        # Método específico, reutiliza BaseRepository.get_by_id()
```

### 2. Service Layer Pattern
Lógica de negócio isolada de rotas.

```python
# Rotas (thin)
@app.post("/plans")
def create_plan(request: PlanCreate, db: Session):
    result = PlanService.create(db, request)
    return result

# Service (business logic)
class PlanService:
    @staticmethod
    def create(db: Session, request: PlanCreate):
        # Validate
        # Transform
        # Persist
        # Queue async tasks
```

### 3. Constants Consolidation
Magic strings centralizados.

```python
# app/constants.py
class PlanActions(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    NOOP = "NOOP"

# Uso
if item.action == PlanActions.CREATE:
    # Sem "CREATE" string mágica
```

### 4. Multi-Tenancy
Isolamento por tenant_id.

```python
# Toda query filtra por tenant_id
db.query(ModelModel).filter(
    ModelModel.tenant_id == tenant_id,
    ...
).first()

# Sem acesso acidental a dados de outros tenants
```

---

## 🔐 Segurança

### Autenticação
- **OAuth2 com Bling** - User login via Bling
- **JWT Tokens** - Para API requests
- **Refresh Tokens** - Bling token refresh handling

### Autorização
- **Tenant Isolation** - Cada query filtra por tenant_id
- **RBAC** (Future) - Role-Based Access Control

### Validação
- **Pydantic Schemas** - Request validation
- **Type Hints** - Static type checking
- **Input Sanitization** - SQL injection prevention

---

## ⚡ Performance

### Caching
- **Bling SKU Cache** - 5 min TTL (Redis)
- **Token Cache** - 30 min TTL (Memory)
- **Query Results** - 1 hour TTL (Redis)

### Optimization
- **Bulk Operations** - Batch Bling API calls
- **Connection Pooling** - PostgreSQL connection reuse
- **Lazy Loading** - Frontend component splitting

---

## 📈 Escalabilidade

### Horizontal Scaling
1. **API Server** - Multiple FastAPI instances behind load balancer
2. **Workers** - Multiple Celery workers for async tasks
3. **Database** - Read replicas for queries

### Vertical Scaling
1. **Caching** - Redis cluster for distributed cache
2. **Database** - Better indexes on frequently queried columns
3. **Batch Size** - Tune `BLING_BATCH_SIZE` per capacity

---

## 🧪 Testing

### Estratégia
- **Unit Tests** - Repositories, services (60%)
- **Integration Tests** - API endpoints (25%)
- **E2E Tests** - Full wizard flow (15%)

### Tools
- **pytest** - Test framework
- **unittest.mock** - Mocking
- **pytest-asyncio** - Async tests
- **SQLAlchemy test fixtures** - DB isolation

---

## 📚 Decisões Arquiteturais

| Decisão | Razão | Alternativas |
|---------|-------|--------------|
| FastAPI | Async, fast, type-safe | Django, Flask |
| PostgreSQL | ACID, JSON support | MongoDB, MySQL |
| SQLAlchemy ORM | Pythonic, migrations | Raw SQL |
| Celery | Distributed tasks | APScheduler, RQ |
| Redis | Caching, sessions, queues | Memcached, in-memory |
| React | Interactive UI | Vue, Angular |
| BaseRepository | DRY, consistency | No inheritance |

---

## 🚀 Deployment

### Development
```bash
docker-compose up                    # Postgres + Redis
python run.py                        # Server
python celery_worker.py             # Worker
npm run dev                         # Frontend
```

### Production (Future)
```bash
# Docker container orchestration (K8s or Docker Swarm)
# Managed database (RDS, Cloud SQL)
# Managed cache (ElastiCache, Memorystore)
# CDN for static assets
# Monitoring (DataDog, Prometheus)
```

---

## 📞 Próximos Passos

1. **FASE 2** - Frontend components refactoring
2. **FASE 3** - Documentação de API (OpenAPI/Swagger)
3. **FASE 4** - Testes automatizados (80%+ coverage)
4. **FASE 5** - CI/CD (GitHub Actions)

Veja [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) para detalhes completos.
