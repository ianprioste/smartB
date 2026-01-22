# ⚡ QUICKSTART - 5 min para rodar

**smartBling v2** com Backend (FastAPI) + Frontend (React Admin).

---

## 📋 Pré-requisitos

- **Python 3.11+** (Windows/Mac/Linux)
- **Node.js 18+** (para React)
- **Docker** (PostgreSQL + Redis)
- **Credenciais Bling** (Client ID + Secret)

```bash
# Verificar versões
python --version   # 3.11+
node --version     # 18+
docker --version
```

---

## 🚀 Setup Backend (5 min)

### 1️⃣ Configure Variáveis de Ambiente

```bash
cd backend
cp .env.example .env
```

**Edite `.env`:**
```
BLING_CLIENT_ID=seu_client_id
BLING_CLIENT_SECRET=seu_secret
BLING_CALLBACK_URL=http://localhost:8000/auth/bling/callback

DATABASE_URL=postgresql+psycopg://smartbling:password@localhost/smartbling_db
REDIS_URL=redis://localhost:6379

JWT_SECRET=seu_secret_aqui_mudar_em_prod
REQUEST_ID_HEADER=X-Request-ID
```

[Obter credenciais Bling](https://developer.bling.com.br/)

### 2️⃣ Inicie PostgreSQL + Redis

```bash
cd backend
docker-compose up -d
```

✅ PostgreSQL 15 em `localhost:5432`  
✅ Redis 7 em `localhost:6379`

### 3️⃣ Instale Dependências

```bash
# Criar virtual env (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Instalar
pip install -r requirements.txt
```

### 4️⃣ Execute Migrations

```bash
# Sprint 1 + Sprint 2
alembic upgrade head
```

```
INFO [alembic.runtime.migration] Running upgrade  -> 001_initial, 
INFO [alembic.runtime.migration] Running upgrade 001_initial -> 002_sprint2_governance
```

### 5️⃣ Inicie Server

**Terminal 1:**
```bash
python run.py
```

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ API: **http://localhost:8000/docs** (Swagger)

### 6️⃣ Inicie Worker Async (opcional)

**Terminal 2:**
```bash
python celery_worker_windows.py
```

```
celery@LAPTOP ready.
```

---

## 🎨 Setup Frontend (3 min)

### 1️⃣ Instale Dependências

```bash
cd frontend
npm install
```

### 2️⃣ Inicie Dev Server

```bash
npm run dev
```

```
VITE v5.0.0  ready in 200 ms
➜  Local:   http://localhost:5173/
```

✅ Admin UI: **http://localhost:5173** (Auto-refresh)

---

## ✅ Validar Setup

### Backend Endpoints

```bash
# 1. Listar modelos
curl -X GET "http://localhost:8000/config/models" \
  -H "X-Tenant-ID: tenant-1"

# 2. Criar modelo
curl -X POST "http://localhost:8000/config/models" \
  -H "X-Tenant-ID: tenant-1" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "CAM",
    "name": "Camiseta",
    "allowed_sizes": ["P", "M", "G", "GG"],
    "size_order": ["P", "M", "G", "GG"]
  }'

# 3. Buscar produtos Bling
curl -X GET "http://localhost:8000/bling/products/search?q=camiseta&limit=5"

# 4. Swagger
open http://localhost:8000/docs
```

### Frontend

1. Acesse **http://localhost:5173**
2. Clique em **"Modelos"** (sidebar)
3. Adicione um modelo novo com tamanhos
4. Clique em **"Templates"**
5. Busque produtos Bling e crie um template

---

## 🐛 Troubleshooting

### ❌ Erro: `connection refused on 5432`

```bash
# Verificar containers
docker ps

# Se não estiverem rodando
cd backend
docker-compose up -d --force-recreate
```

### ❌ Erro: `module not found 'app'`

```bash
# Verificar se está no diretório correto
pwd  # deve terminar em /backend

# Recriar venv
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### ❌ Frontend não conecta ao backend

**Verifique:**
- Backend rodando? `http://localhost:8000/docs`
- Frontend em porta 5173? `http://localhost:5173`
- CORS ativado? (veja [DEVELOPMENT.md](DEVELOPMENT.md#cors))

### ❌ Alembic: `version conflict`

```bash
# Reset migrations (dev only!)
docker exec smartbling-postgres psql -U smartbling smartbling_db \
  -c "DROP TABLE alembic_version;"

alembic upgrade head
```

---

## 📚 Próximos Passos

1. **[Documentação Técnica](README.md)** - Arquitetura e decisões
2. **[SPRINT2_SUMMARY.md](SPRINT2_SUMMARY.md)** - O que foi entregue
3. **[EXAMPLES.md](EXAMPLES.md)** - Exemplos práticos
4. **[DEVELOPMENT.md](DEVELOPMENT.md)** - Como contribuir

---

## 🎯 Checklists

### ✅ Backend Ready
- [ ] PostgreSQL rodando (`docker ps`)
- [ ] `alembic upgrade head` executado
- [ ] `python run.py` mostra "Uvicorn running"
- [ ] `http://localhost:8000/docs` acessível

### ✅ Frontend Ready
- [ ] Node 18+ instalado
- [ ] `npm install` completado
- [ ] `npm run dev` mostra porta 5173
- [ ] `http://localhost:5173` acessível

### ✅ Full Stack Ready
- [ ] POST /config/models com sucesso
- [ ] GET /config/models retorna dados
- [ ] Frontend carrega 3 abas (Modelos, Cores, Templates)
- [ ] Busca Bling funciona

---

**Versão:** 0.2.0 (Sprint 2)  
**Tempo Total:** ~10 min  
**Próxima:** Deploy local completo
