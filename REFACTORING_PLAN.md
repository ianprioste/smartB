# 🔧 Plano de Refatoração Completa - smartBling v2

## 📋 Escopo da Refatoração

Este documento detalha o plano completo para refatorar o projeto **smartBling v2**, incluindo:
- ✅ Backend (padrões, constants, base classes)
- ✅ Frontend (componentes, organização)
- ✅ Documentação (consolidação, clareza)
- ✅ Configuração (env, scripts)
- ✅ Testes (estrutura base)

---

## 🎯 Objetivos

| Objetivo | Métrica | Status |
|----------|---------|--------|
| Reduzir duplicação | -30% linhas duplicadas | ⏳ |
| Melhorar manutenibilidade | Componentes <300 linhas | ⏳ |
| Clarificar código | 100% constants consolidadas | ⏳ |
| Documentação completa | README + DEVELOPMENT + API | ⏳ |
| Testes estruturados | Base estrutura pronta | ⏳ |

---

## 📊 Estrutura de Fases

### **FASE 1: Backend Core (4 horas)**
- [ ] 1.1 Criar constants.py centralizado
- [ ] 1.2 Implementar BaseRepository
- [ ] 1.3 Consolidar schemas e DTOs
- [ ] 1.4 Refatorar plan_execution.py helpers
- [ ] 1.5 Otimizar BlingClient

### **FASE 2: Frontend Components (3 horas)**
- [ ] 2.1 Split AdminPages.jsx em componentes
- [ ] 2.2 Split WizardNew.jsx em componentes
- [ ] 2.3 Criar hooks customizados
- [ ] 2.4 Organizar styles/estrutura
- [ ] 2.5 Implementar error boundaries

### **FASE 3: Documentação (2 horas)**
- [ ] 3.1 Atualizar README.md com links corretos
- [ ] 3.2 Criar ARCHITECTURE.md detalhado
- [ ] 3.3 Criar API.md com endpoints
- [ ] 3.4 Criar TESTING.md com guias
- [ ] 3.5 Criar DEPLOYMENT.md

### **FASE 4: Testes & Estrutura (3 horas)**
- [ ] 4.1 Configurar pytest com fixtures
- [ ] 4.2 Implementar testes de repositórios
- [ ] 4.3 Implementar testes de API
- [ ] 4.4 Setup CI/CD básico (GitHub Actions)
- [ ] 4.5 Criar conftest.py com mocks

### **FASE 5: Configuração & Deploy (2 horas)**
- [ ] 5.1 Consolidar .env files
- [ ] 5.2 Criar docker-compose.prod.yml
- [ ] 5.3 Setup script de backup
- [ ] 5.4 Criar CONTRIBUTING.md
- [ ] 5.5 Limpar arquivos desnecessários

---

## 🔍 Detalhes por Fase

### FASE 1: Backend Core

#### 1.1 Constants Centralizados
**Localização:** `backend/app/constants.py`

```python
class PlanActions:
    """Plan item actions."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    NOOP = "NOOP"
    BLOCKED = "BLOCKED"

class EntityTypes:
    """Product entity types."""
    BASE_PLAIN = "BASE_PLAIN"
    PARENT_PRINTED = "PARENT_PRINTED"
    VARIATION_PRINTED = "VARIATION_PRINTED"
    BASE_PARENT = "BASE_PARENT"
    BASE_VARIATION = "BASE_VARIATION"

class StatusCodes:
    """HTTP status codes."""
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
```

**Arquivos a atualizar:**
- `plan_execution.py` - usar `PlanActions.CREATE` em vez de `"CREATE"`
- `wizard_new.py` - usar `EntityTypes.*`
- `plans.py` - usar `StatusCodes.*`

---

#### 1.2 BaseRepository Implementation
**Localização:** `backend/app/repositories/base.py`

**Métodos comuns a consolidar:**
```python
@classmethod
def get_by_id(cls, db: Session, tenant_id: UUID, id: UUID)
@classmethod
def list_all(cls, db: Session, tenant_id: UUID)
@classmethod
def list_with_filter(cls, db: Session, tenant_id: UUID, **filters)
@classmethod
def delete(cls, db: Session, id: UUID)
@classmethod
def create(cls, db: Session, **kwargs)
```

**Subclasses a atualizar:**
- `ModelRepository`
- `ColorRepository`
- `TemplateRepository`
- `BlingTokenRepository`

---

#### 1.3 Schemas Consolidação
**Problema:** Schemas duplicados em múltiplos arquivos
**Solução:** Consolidar em `backend/app/schemas.py`

**Estrutura:**
```
schemas/
├── __init__.py
├── models.py          # ModelCreate, ModelUpdate, ModelResponse
├── colors.py          # ColorCreate, ColorUpdate, ColorResponse
├── templates.py       # TemplateResponse, TemplateLookup
├── plans.py           # PlanCreate, PlanResponse
├── products.py        # ProductResponse
└── base.py            # BaseSchema com timestamps
```

---

#### 1.4 Plan Execution Helpers
**Arquivo:** `backend/app/api/plan_execution.py`

**Já refatorado - consolidar imports:**
```python
# Usar as funções consolidadas:
- parse_color_and_size()      # Substituiu 2 funções
- extract_dependencies()       # Substituiu 2 funções
- _build_color_map()          # Reutilizável
- _merge_variations()         # Lógica clara
```

---

#### 1.5 BlingClient Otimização
**Localização:** `backend/app/infra/bling_client.py`

**Melhorias:**
- [ ] Cache de token em memória (30min TTL)
- [ ] Retry automático com backoff exponencial
- [ ] Rate limiting local (300 req/min)
- [ ] Batch operations helper
- [ ] Type hints completos

---

### FASE 2: Frontend Components

#### 2.1 AdminPages.jsx Split

**Antes:** 710 linhas em 1 arquivo  
**Depois:** ~200 linhas no main + componentes menores

**Estrutura:**
```
frontend/src/pages/admin/
├── AdminPages.jsx                    # ~200 linhas - container
├── components/
│   ├── ModelTable.jsx               # ~150 linhas
│   ├── ColorTable.jsx               # ~150 linhas
│   ├── TemplateSearch.jsx           # ~200 linhas
│   ├── TemplateTable.jsx            # ~150 linhas
│   ├── AddItemModal.jsx             # ~100 linhas
│   └── ReauthModal.jsx              # ~80 linhas
└── hooks/
    ├── useAdmin.js                  # ~80 linhas
    └── useTemplateSearch.js         # ~60 linhas
```

---

#### 2.2 WizardNew.jsx Split

**Antes:** 589 linhas em 1 arquivo  
**Depois:** ~150 linhas no main + componentes menores

**Estrutura:**
```
frontend/src/pages/wizard/
├── WizardNew.jsx                    # ~150 linhas - container
├── components/
│   ├── Step1_PrintInfo.jsx          # ~100 linhas
│   ├── Step2_Models.jsx             # ~100 linhas
│   ├── Step3_Colors.jsx             # ~100 linhas
│   ├── Step4_Templates.jsx          # ~150 linhas
│   ├── Step5_Review.jsx             # ~120 linhas
│   ├── PlanPreview.jsx              # ~100 linhas
│   └── LoadingModal.jsx             # ~80 linhas
└── hooks/
    └── useWizard.js                 # ~100 linhas
```

---

#### 2.3 Hooks Customizados

**useAdmin.js:** Gerencia estado de admin
```javascript
const useAdmin = () => {
  const [models, setModels] = useState([])
  const [colors, setColors] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)
  
  const fetchModels = useCallback(async () => { ... }, [])
  const fetchColors = useCallback(async () => { ... }, [])
  
  return { models, colors, templates, loading, fetchModels, ... }
}
```

**useWizard.js:** Gerencia estado do wizard
```javascript
const useWizard = () => {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({})
  const [plan, setPlan] = useState(null)
  
  const nextStep = useCallback(() => { ... }, [])
  const submitPlan = useCallback(async () => { ... }, [])
  
  return { step, formData, plan, nextStep, ... }
}
```

---

#### 2.4 Styles Organização

```
frontend/src/styles/
├── index.css                        # Variáveis globais
├── components/
│   ├── tables.css
│   ├── modals.css
│   ├── forms.css
│   └── buttons.css
├── pages/
│   ├── admin.css
│   └── wizard.css
└── utilities/
    ├── spacing.css
    └── typography.css
```

---

#### 2.5 Error Boundaries

**frontend/src/components/ErrorBoundary.jsx:**
```javascript
export class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    // Log, mostrar fallback UI
  }
}
```

---

### FASE 3: Documentação

#### 3.1 README.md Atualizado
- ✅ Links corretos para doc/
- ✅ Quick start melhorado
- ✅ Badges de status
- ✅ Contributing section
- ✅ License

#### 3.2 ARCHITECTURE.md
- Diagrama de componentes
- Fluxo de dados
- Camadas (API, Domain, Infra)
- Padrões de design
- Decisões arquiteturais

#### 3.3 API.md
- Todos os endpoints com exemplos
- Request/Response schemas
- Códigos de erro
- Autenticação
- Rate limiting

#### 3.4 TESTING.md
- Como rodar testes
- Estrutura de testes
- Fixtures e mocks
- Coverage targets

#### 3.5 DEPLOYMENT.md
- Setup produção
- Variáveis de ambiente
- Scaling
- Monitoring
- Backup/Restore

---

### FASE 4: Testes & Estrutura

#### 4.1 pytest Setup
```
backend/tests/
├── conftest.py                      # Fixtures globais
├── fixtures/
│   ├── database.py
│   ├── client.py
│   └── mocks.py
├── unit/
│   ├── test_repositories.py
│   ├── test_schemas.py
│   └── test_helpers.py
├── integration/
│   ├── test_api_auth.py
│   ├── test_api_models.py
│   └── test_api_plans.py
└── e2e/
    └── test_wizard_flow.py
```

#### 4.2 Fixtures Base
```python
@pytest.fixture
def db():
    """Database fixture."""

@pytest.fixture
def client():
    """Test client fixture."""

@pytest.fixture
def mock_bling_client():
    """Mock Bling client."""

@pytest.fixture
def authenticated_user():
    """User with valid token."""
```

---

### FASE 5: Configuração & Deploy

#### 5.1 .env Consolidado
```
# backend/.env.example
# Core
DEBUG=False
ENVIRONMENT=production

# Database
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=smartbling
POSTGRES_USER=smartbling

# Redis/Celery
REDIS_URL=redis://redis:6379/0

# Bling
BLING_CLIENT_ID=...
BLING_REDIRECT_URI=...

# App
ADMIN_PANEL_URL=https://admin.smartbling.local
API_URL=https://api.smartbling.local

# Logging
LOG_LEVEL=INFO
```

#### 5.2 docker-compose.prod.yml
```yaml
version: '3.9'

services:
  db:
    image: postgres:15-alpine
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: always

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "80:80"

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    restart: always
```

---

## 📈 Métricas de Sucesso

| Métrica | Antes | Depois | Status |
|---------|-------|--------|--------|
| Linhas duplicadas | ~500 | ~200 | ⏳ |
| Maior componente | 710 | 200 | ⏳ |
| Cobertura de testes | 0% | 70%+ | ⏳ |
| Constants centralizadas | 0% | 100% | ⏳ |
| Documentação | 60% | 100% | ⏳ |

---

## 🚀 Timeline Estimada

- **Semana 1:** Fase 1 (Backend Core) - 4 horas
- **Semana 2:** Fase 2 (Frontend) - 3 horas
- **Semana 3:** Fase 3 (Documentação) - 2 horas
- **Semana 4:** Fase 4-5 (Testes & Deploy) - 5 horas

**Total: ~14 horas de trabalho**

---

## ✅ Checklist de Implementação

Use este checklist para acompanhar o progresso:

```
FASE 1: Backend Core
[ ] 1.1 constants.py criado e importado
[ ] 1.2 BaseRepository implementado
[ ] 1.3 Schemas consolidados
[ ] 1.4 plan_execution.py refatorado
[ ] 1.5 BlingClient otimizado

FASE 2: Frontend Components
[ ] 2.1 AdminPages.jsx split
[ ] 2.2 WizardNew.jsx split
[ ] 2.3 Hooks customizados
[ ] 2.4 Styles organizados
[ ] 2.5 Error boundaries

FASE 3: Documentação
[ ] 3.1 README.md atualizado
[ ] 3.2 ARCHITECTURE.md criado
[ ] 3.3 API.md criado
[ ] 3.4 TESTING.md criado
[ ] 3.5 DEPLOYMENT.md criado

FASE 4: Testes & Estrutura
[ ] 4.1 pytest setup
[ ] 4.2 Fixtures implementadas
[ ] 4.3 Testes de repositórios
[ ] 4.4 Testes de API
[ ] 4.5 CI/CD básico

FASE 5: Configuração
[ ] 5.1 .env consolidado
[ ] 5.2 docker-compose.prod.yml
[ ] 5.3 Scripts de deploy
[ ] 5.4 CONTRIBUTING.md
[ ] 5.5 Limpeza geral
```

---

## 📞 Suporte

- **Dúvidas arquiteturais:** Consulte ARCHITECTURE.md
- **Exemplos de código:** Consulte EXAMPLES.md
- **Setup local:** Consulte QUICKSTART.md
- **Deploy:** Consulte DEPLOYMENT.md
