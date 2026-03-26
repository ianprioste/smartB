# smartBling v2 - SaaS com Bling ERP 🚀

Integração SaaS com Bling ERP (API v3) com **Sprint 1 (Foundation) + Sprint 2 (Governance)** completos.

**Stack:** FastAPI + PostgreSQL + Redis + Celery + React (Admin UI)

## 📚 Documentação

### 🏃 Comece Aqui
- **[INDEX.md](doc/INDEX.md)** - Hub da documentação
- **[QUICKSTART.md](doc/QUICKSTART.md)** ⭐ - 5 minutos para rodar

### 🎪 Sistema de Eventos de Vendas (Novo!)
- **[SALES_EVENTS_README.md](SALES_EVENTS_README.md)** ✨ - Guia completo e tutoriais
- **[doc/SALES_EVENTS_IMPLEMENTATION.md](doc/SALES_EVENTS_IMPLEMENTATION.md)** - Detalhes técnicos da implementação

### 📖 Guias Principais
- **[ARCHITECTURE.md](doc/ARCHITECTURE.md)** - Visão completa e diagramas
- **[API.md](doc/API.md)** - Endpoints, exemplos e erros
- **[TESTING.md](doc/TESTING.md)** - Estratégia de testes e fixtures
- **[DEPLOYMENT.md](doc/DEPLOYMENT.md)** - Dev/Staging/Produção e checklists
- **[PROJECT_STRUCTURE.md](doc/PROJECT_STRUCTURE.md)** - Estrutura de código
- **[DEVELOPMENT.md](doc/DEVELOPMENT.md)** - Fluxo de desenvolvimento
- **[WINDOWS_SETUP.md](doc/WINDOWS_SETUP.md)** - Setup para Windows

---

## 🚀 Quick Start

```bash
# Backend
cd backend
cp .env.example .env
# Edite .env com credenciais Bling

docker-compose up -d              # PostgreSQL + Redis
pip install -r requirements.txt
alembic upgrade head              # Sprint 2 migrations

# Terminal 1: Server
python run.py

# Terminal 2: Worker
python celery_worker_windows.py

# Frontend
cd ../frontend
npm install
npm run dev
```

🎉 API: http://localhost:8000/docs  
🎨 Admin UI: http://localhost:5173

---

## 📁 Estrutura

```
.
├── doc/                          # 📚 Documentação (9 files)
├── scripts/                      # 🔧 Inicialização
├── project/                      # 📋 Status docs
├── backend/                      # 🚀 FastAPI
│   ├── app/
│   │   ├── api/                  # Endpoints (auth, jobs, config, bling)
│   │   ├── infra/                # DB, Bling, Logging
│   │   ├── models/               # ORM + Schemas + Enums
│   │   ├── repositories/         # Data access
│   │   └── workers/              # Celery
│   ├── alembic/versions/         # 002_sprint2_governance
│   └── run.py
└── frontend/                     # ⚛️ React + Vite
    ├── src/
    │   ├── pages/admin/          # 3 páginas (Models, Colors, Templates)
    │   └── styles/
    └── package.json
```

---

## ✨ Features

| Feature | Status | Sprint |
|---------|--------|--------|
| 🔐 OAuth2 + Bling | ✅ | Sprint 1 |
| 🤖 BlingClient robusto | ✅ | Sprint 1 |
| 📦 Jobs async | ✅ | Sprint 1 |
| 📊 Logging JSON | ✅ | Sprint 1 |
| 🛢️ PostgreSQL + Alembic | ✅ | Sprint 1 |
| 📋 Modelos (CRUD) | ✅ | Sprint 2 |
| 🎨 Cores (CRUD) | ✅ | Sprint 2 |
| 🎯 Templates (Bling lookup) | ✅ | Sprint 2 |
| 💻 Admin UI (React) | ✅ | Sprint 2 |
| 🧪 Tests | ❌ | Sprint 3 |
| 🛡️ JWT API Auth | ❌ | Sprint 3 |
| 📦 Produtos (criar/sync) | ❌ | Sprint 3 |

---

## 🏗️ Arquitetura

**7-Layer Clean + Multi-tenant:**

```
API Layer (FastAPI)
    ↓
Repositories (Data Access)
    ↓
Models (ORM + Validation)
    ↓
Infrastructure (DB, HTTP, Logging)
    ↓
Workers (Async Tasks)
```

---

## 🔌 Endpoints

### Autenticação (Sprint 1)
- `POST /auth/bling/connect` - OAuth2 URL
- `GET /auth/bling/callback` - Callback + token storage

### Jobs (Sprint 1)
- `POST/GET /jobs` - CRUD
- `GET /jobs/{id}/detail` - Com items

### Config - Modelos (Sprint 2)
- `GET/POST /config/models`
- `PUT/DELETE /config/models/{code}`

### Config - Cores (Sprint 2)
- `GET/POST /config/colors`
- `PUT/DELETE /config/colors/{code}`

### Config - Templates (Sprint 2)
- `GET/POST /config/templates`
- `DELETE /config/templates/{id}`

### Bling Products (Sprint 2)
- `GET /bling/products/search?q=...`
- `GET /bling/products/{id}`

---

## 🎯 DoD Sprint 2 (Completo)

✅ Modelos: cadastro com allowed_sizes, validação  
✅ Cores: cadastro CRUD  
✅ Templates: busca Bling + persistência  
✅ Admin UI: 3 páginas funcionais  
✅ Multi-tenant: todos endpoints salvam tenant_id  
✅ Migrations: 002_sprint2_governance.py  
✅ Logs: request_id + tenant_id (sem tokens)  
✅ Validações: conforme escopo  

---

## 🚀 Próximos Passos

**Sprint 3: Products**
- Criar/atualizar produtos no Bling
- Sincronizar atributos (tamanho, cor, preço)
- Mapeamento SKU

**Sprint 4: Inventory**
- Sync de estoque
- Webhooks Bling
- Alertas

**Sprint 5: UI Dashboard**
- React dashboard com charts
- Logs em tempo real

---

**Versão:** 0.2.0  
**Status:** ✅ Sprint 1 + 2 completo  
**Branches:** `main` (protected) | `dev` (work)  
**Repo:** github.com/ianprioste/smartB

## 🔗 Endpoints Principais

### Authentication
- `POST /auth/bling/connect` - Gera URL OAuth2
- `GET /auth/bling/callback` - Callback automático

### Jobs
- `POST /jobs` - Cria job
- `GET /jobs` - Lista jobs
- `GET /jobs/{id}` - Detalhes
- `GET /jobs/{id}/items` - Items do job
- `DELETE /jobs` - Apaga todos (dev)

---

## 🛠️ Scripts

Localizados em `/scripts`:

```bash
# Iniciar server
./scripts/start_server.bat     # Windows
./scripts/start_server.sh      # Linux/Mac

# Iniciar worker
./scripts/start_worker.bat     # Windows
./scripts/start_worker.sh      # Linux/Mac

# Verificar setup
./scripts/verify.bat           # Windows
./scripts/verify.sh            # Linux/Mac
```

---

## 🔧 Configuração

### Arquivo `.env`

```ini
# Bling OAuth2
BLING_CLIENT_ID=seu_id
BLING_CLIENT_SECRET=seu_secret
BLING_REDIRECT_URI=http://localhost:8000/auth/bling/callback

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smartbling

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Debug
DEBUG=False
LOG_LEVEL=INFO
```

### Bling Setup

1. Vá para: https://www.bling.com.br/oauth/applications
2. Registre aplicação
3. Configure redirect: `http://localhost:8000/auth/bling/callback`
4. Copie Client ID e Secret para `.env`

---

## 📖 Exemplos

### Criar Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type":"sync_products","input_payload":{"action":"full_sync"}}'
```

### Monitorar Job

```bash
curl http://localhost:8000/jobs
curl http://localhost:8000/jobs/{id}
```

Para fluxos completos, consulte a coleção de exemplos nos endpoints em [doc/API.md](doc/API.md).

---

## 🆘 Troubleshooting

### Worker não funciona
```bash
# Windows: .venv deve estar ativado antes de rodar
cd backend
.\.venv\Scripts\Activate.ps1
python celery_worker_windows.py
```

### Port 8000 em uso
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Conexão recusada (Redis/PostgreSQL)
```bash
docker-compose ps
docker-compose logs
```

Mais em [WINDOWS_SETUP.md](doc/WINDOWS_SETUP.md)

---

## 🚀 Próximos Passos

1. **Sprint 2**: Autenticação JWT, endpoints de Produtos
2. **Sprint 3**: Endpoints de Pedidos, validações avançadas
3. **Sprint 4**: Rate limiting, health checks, testes (80%+ coverage)

---

## 📚 Recursos

- [Bling API v3](https://developers.bling.com.br/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Celery](https://docs.celeryproject.io/)
- [PostgreSQL](https://www.postgresql.org/)
- [Redis](https://redis.io/)

---

## 📝 License

Proprietary - smartBling v2

---

**Desenvolvido com ❤️ para integração com Bling ERP v3**
