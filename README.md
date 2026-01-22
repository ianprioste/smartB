# smartBling v2 - Backend SaaS com Bling ERP 🚀

Integração SaaS com Bling ERP (API v3) desenvolvida em **Sprint 1** com FastAPI, OAuth2, Job infrastructure e observabilidade estruturada.

## 📚 Documentação

### 🏃 Comece Aqui
- **[QUICKSTART.md](doc/QUICKSTART.md)** ⭐ - 5 minutos para rodar (passo-a-passo)
- **[README.md](doc/README.md)** - Visão geral completa do projeto

### 📖 Documentação Técnica
- **[DEVELOPMENT.md](doc/DEVELOPMENT.md)** - Arquitetura, decisões técnicas
- **[PROJECT_STRUCTURE.md](doc/PROJECT_STRUCTURE.md)** - Detalhes de cada camada
- **[EXAMPLES.md](doc/EXAMPLES.md)** - Exemplos práticos de uso
- **[SPRINT1_SUMMARY.md](doc/SPRINT1_SUMMARY.md)** - O que foi entregue no Sprint 1
- **[CODE_REVIEW.md](doc/CODE_REVIEW.md)** - Análise de código e melhorias futuras

### ⚙️ Setup e Troubleshooting
- **[WINDOWS_SETUP.md](doc/WINDOWS_SETUP.md)** - Guia específico para Windows

---

## 🚀 Quick Start

```bash
# 1. Configure
cd backend
cp .env.example .env
# Edite .env com suas credenciais Bling

# 2. Inicie serviços
docker-compose up -d

# 3. Instale dependências
pip install -r requirements.txt

# 4. Server (Terminal 1)
python run.py

# 5. Worker (Terminal 2)
python celery_worker_windows.py  # ou celery -A app.workers.celery_app worker
```

🎉 Acesse: http://localhost:8000/docs

---

## 📁 Estrutura

```
.
├── doc/                          # 📚 Documentação
├── scripts/                      # 🔧 Scripts de inicialização
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── api/                 # Endpoints (auth, jobs)
│   │   ├── infra/               # Infrastructure (DB, Bling client, logging)
│   │   ├── models/              # ORM + Schemas
│   │   ├── repositories/        # Data access layer
│   │   └── workers/             # Celery tasks
│   ├── requirements.txt
│   ├── run.py                   # Entry point
│   ├── docker-compose.yml
│   └── alembic/                 # DB migrations
└── README.md                     # Este arquivo
```

---

## ✨ Features

| Feature | Status | Detalhes |
|---------|--------|----------|
| 🔐 OAuth2 Bling | ✅ | Autenticação completa com Bling |
| 🧠 BlingClient | ✅ | Retry automático, logging estruturado |
| 📦 Jobs | ✅ | API + DB + Worker async |
| 📊 Logging | ✅ | JSON estruturado, rastreamento |
| 🗄️ PostgreSQL | ✅ | ORM SQLAlchemy + Migrations |
| 🔄 Redis | ✅ | Cache + Message broker |
| 📡 Celery | ✅ | Worker async (configurable pool) |
| 🧪 Tests | ❌ | Sprint 2 |
| 🛡️ JWT Auth | ❌ | Sprint 2 |
| 📦 Produtos | ❌ | Sprint 2 |

---

## 🏗️ Arquitetura

**7-Layer Clean Architecture:**

1. **API** - FastAPI endpoints (auth, jobs)
2. **Services** - Lógica de negócio (Sprint 2)
3. **Domain** - Entidades e regras
4. **Infrastructure** - DB, Bling client, logging
5. **Models** - ORM (SQLAlchemy) + Schemas (Pydantic)
6. **Repositories** - Data access layer
7. **Workers** - Celery async tasks

---

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

Mais exemplos em [EXAMPLES.md](doc/EXAMPLES.md)

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
