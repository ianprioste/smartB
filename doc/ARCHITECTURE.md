# Arquitetura do Projeto

Documentacao da arquitetura real do sistema no estado atual.

## Visao geral

- Frontend: React + Vite (porta 5173 em desenvolvimento)
- Backend: FastAPI (porta 8000)
- Banco: SQLite ou PostgreSQL via `DATABASE_URL`
- Integracao externa: Bling API (OAuth2)
- Processamento assíncrono: Celery (com fallback local para alguns fluxos)

Fluxo de alto nivel:

1. Usuario acessa o frontend.
2. Frontend chama backend via `/api/*` (proxy do Vite reescreve para `/*` no backend).
3. Backend valida sessao (cookie `smartb_session`) para rotas protegidas.
4. Backend acessa dados locais e/ou Bling API.

## Estrutura principal do backend

Diretorio base: `backend/app`

- `main.py`: cria app FastAPI, middlewares e inclui routers
- `settings.py`: configuracoes da aplicacao
- `api/`: endpoints HTTP
- `repositories/`: acesso a dados
- `domain/`: logica de dominio
- `infra/`: infraestrutura (db, logging, bling client, cache)
- `models/`: ORM e schemas
- `workers/`: tarefas assíncronas

Entradas do backend:

- `backend/run.py`: sobe API via Uvicorn (`app.main:app`)
- `backend/celery_worker.py`: worker Celery

## API ativa (modulos)

Routers principais em `backend/app/api`:

- `auth.py` (`/auth`) - OAuth2 Bling
- `access_control.py` (`/auth/access`) - login/sessao/perfis/usuarios
- `config_models.py` (`/config/models`)
- `config_colors.py` (`/config/colors`)
- `config_templates.py` (`/config/templates`)
- `bling_products.py` (`/bling/products`)
- `plans.py` (`/plans`) - geracao e persistencia de planos
- `plan_execution.py` (`/plans`) - execucao de planos
- `orders.py` (`/orders`) - sincronizacao e operacao de pedidos
- `events.py` (`/events`) - eventos de vendas
- `dashboard.py` (`/dashboard`) - indicadores
- `jobs.py` (`/jobs`) - rastreamento de jobs

## Autenticacao e autorizacao

- Login local: `POST /auth/access/login`
- Sessao armazenada em cookie HTTP-only `smartb_session`
- Middleware em `app/main.py` protege rotas nao publicas
- Rotas publicas incluem `health`, `docs`, `redoc`, `openapi.json`, login/bootstrap e OAuth Bling

## Persistencia e modelo de dados

Banco definido por `DATABASE_URL`.

Entidades importantes (arquivo `backend/app/models/database.py`):

- acesso: `AccessProfileModel`, `AccessUserModel`, `AccessSessionModel`
- bling auth: `BlingTokenModel`
- catalogo: `ModelModel`, `ColorModel`, `ModelTemplateModel`
- planejamento: `PlanModel`, `JobModel`, `JobItemModel`
- pedidos/eventos: `BlingOrderSnapshotModel`, `BlingOrderSyncStateModel`, `SalesEventModel`, `SalesEventProductModel`, `ItemProductionNoteModel`
- tenancy: `TenantModel` (tenant default criado no startup)

Migracoes com Alembic em `backend/alembic`.

## Sincronizacao de pedidos

- Endpoint full: `POST /orders/sync/full`
- Endpoint incremental: `POST /orders/sync/incremental`
- Status: `GET /orders/sync/status`
- O sistema usa snapshots locais para consultas de pedidos na UI.
- Em ambientes sem worker, parte do fluxo pode usar fallback local em background.

## Frontend atual

Diretorio base: `frontend/src`

- `App.jsx`: roteamento e guards
- `pages/`
  - `auth/LoginPage.jsx`
  - `home/HomePage.jsx`
  - `orders/OrdersPage.jsx`
  - `events/EventCreatePage.jsx`
  - `events/EventSalesPage.jsx`
  - `products/ProductsListPage.jsx`
  - `wizard/WizardNew.jsx`
  - `wizard/WizardPlain.jsx`
  - `admin/AdminPages.jsx`
  - `admin/AccessControlPage.jsx`
- `components/Layout.jsx` e componentes de apoio
- `components/ProductionControls.jsx` usado em pedidos/eventos para controles de producao

## Configuracao de ambiente

Variaveis relevantes (backend):

- `DATABASE_URL`
- `BLING_CLIENT_ID`
- `BLING_CLIENT_SECRET`
- `BLING_REDIRECT_URI`
- `REDIS_URL`
- `SECRET_KEY`

Arquivo base: `backend/.env.example`.

## Observacoes de deploy

- Docker nao e requisito para o projeto atual.
- Deploy padrao documentado em [DEPLOYMENT.md](DEPLOYMENT.md).

## Referencias

- [API.md](API.md)
- [QUICKSTART.md](QUICKSTART.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [SALES_EVENTS_IMPLEMENTATION.md](SALES_EVENTS_IMPLEMENTATION.md)
