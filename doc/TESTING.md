# 🧪 Testing Guide - smartBling v2

## 📋 Visão Geral

Esta guia descreve a estratégia de testes, estrutura, e como executar testes no projeto.

### Estatísticas Alvo

| Categoria | Target | Status |
|-----------|--------|--------|
| Cobertura Total | 80%+ | ⏳ |
| Unit Tests | 60% | ⏳ |
| Integration Tests | 25% | ⏳ |
| E2E Tests | 15% | ⏳ |

---

## 🏗️ Estrutura de Testes

```
backend/tests/
├── conftest.py                    # Pytest configuration & fixtures
├── __init__.py
│
├── fixtures/
│   ├── __init__.py
│   ├── database.py               # DB fixtures
│   ├── client.py                 # Test client fixtures
│   ├── mocks.py                  # Mock objects
│   └── auth.py                   # Auth fixtures
│
├── unit/                         # Unit Tests (~60%)
│   ├── test_repositories.py
│   ├── test_services.py
│   ├── test_schemas.py
│   ├── test_helpers.py
│   └── test_constants.py
│
├── integration/                  # Integration Tests (~25%)
│   ├── test_api_auth.py
│   ├── test_api_admin.py
│   ├── test_api_plans.py
│   └── test_plan_execution.py
│
└── e2e/                         # End-to-End Tests (~15%)
    ├── test_wizard_flow.py      # Complete wizard -> execution
    └── test_error_scenarios.py
```

---

## 🛠️ Setup

### 1. Instalar Dependências de Teste

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov pytest-mock
```

### 2. Arquivo conftest.py

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base
from app.main import app
from fastapi.testclient import TestClient

# In-memory SQLite for tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    engine = create_engine(
        SQLALCHEMY_TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db(engine):
    """Create test database session."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db):
    """Create test client with injected DB."""
    def override_get_db():
        yield db
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_bling_client(mocker):
    """Mock Bling API client."""
    mock_client = mocker.AsyncMock()
    mock_client.get = mocker.AsyncMock()
    mock_client.post = mocker.AsyncMock()
    mock_client.put = mocker.AsyncMock()
    return mock_client

@pytest.fixture
def authenticated_user(db):
    """Create authenticated test user."""
    user = UserModel(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        email="test@example.com",
        name="Test User",
    )
    db.add(user)
    db.commit()
    return user
```

---

## 📝 Escrevendo Testes

### Unit Tests - Repositórios

```python
# backend/tests/unit/test_repositories.py
import pytest
from uuid import UUID
from app.models.database import ModelModel
from app.repositories.model_repo import ModelRepository

@pytest.fixture
def tenant_id():
    return UUID("00000000-0000-0000-0000-000000000001")

@pytest.fixture
def sample_model(db, tenant_id):
    """Create sample model for tests."""
    model = ModelModel(
        tenant_id=tenant_id,
        code="MODELO01",
        name="Test Model",
        allowed_sizes=["P", "M", "G"],
    )
    db.add(model)
    db.commit()
    return model

class TestModelRepository:
    """Tests for ModelRepository."""
    
    def test_create(self, db, tenant_id):
        """Test creating a new model."""
        model = ModelRepository.create(
            db,
            tenant_id=tenant_id,
            code="TEST01",
            name="Test",
            allowed_sizes=["P", "M"],
            size_order=["P", "M"],
        )
        
        assert model.id is not None
        assert model.code == "TEST01"
        assert model.name == "Test"
    
    def test_get_by_id(self, db, tenant_id, sample_model):
        """Test retrieving model by ID."""
        retrieved = ModelRepository.get_by_id(db, tenant_id, sample_model.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_model.id
        assert retrieved.code == "MODELO01"
    
    def test_get_by_id_wrong_tenant(self, db):
        """Test that get_by_id respects tenant isolation."""
        other_tenant = UUID("99999999-9999-9999-9999-999999999999")
        retrieved = ModelRepository.get_by_id(db, other_tenant, UUID("fake-id"))
        
        assert retrieved is None
    
    def test_get_by_code(self, db, tenant_id, sample_model):
        """Test retrieving model by code."""
        retrieved = ModelRepository.get_by_code(db, tenant_id, "MODELO01")
        
        assert retrieved is not None
        assert retrieved.code == "MODELO01"
    
    def test_list_active(self, db, tenant_id, sample_model):
        """Test listing active models."""
        models = ModelRepository.list_active(db, tenant_id)
        
        assert len(models) == 1
        assert models[0].code == "MODELO01"
    
    def test_list_active_excludes_inactive(self, db, tenant_id, sample_model):
        """Test that inactive models are excluded."""
        sample_model.is_active = False
        db.commit()
        
        models = ModelRepository.list_active(db, tenant_id)
        
        assert len(models) == 0
    
    def test_update(self, db, tenant_id, sample_model):
        """Test updating a model."""
        updated = ModelRepository.update_from_request(
            db,
            tenant_id,
            "MODELO01",
            ModelUpdateRequest(name="Updated Name"),
        )
        
        assert updated.name == "Updated Name"
    
    def test_soft_delete(self, db, tenant_id, sample_model):
        """Test soft delete (mark inactive)."""
        deleted = ModelRepository.soft_delete(db, tenant_id, "MODELO01")
        
        assert deleted is True
        assert sample_model.is_active is False
```

### Unit Tests - Services

```python
# backend/tests/unit/test_services.py
import pytest
from unittest.mock import Mock, AsyncMock
from app.services.plan_service import PlanService

@pytest.mark.asyncio
async def test_create_plan_valid_input(mock_bling_client):
    """Test creating plan with valid input."""
    plan_data = {
        "print_specs": {...},
        "models": [...],
        "colors": [...],
    }
    
    plan = await PlanService.create(mock_bling_client, plan_data)
    
    assert plan.id is not None
    assert plan.status == "PENDING"

@pytest.mark.asyncio
async def test_create_plan_invalid_models(mock_bling_client):
    """Test creating plan with invalid models."""
    plan_data = {
        "models": [],  # Empty
    }
    
    with pytest.raises(ValueError, match="At least one model required"):
        await PlanService.create(mock_bling_client, plan_data)
```

### Integration Tests - API

```python
# backend/tests/integration/test_api_admin.py
import pytest

class TestAdminAPI:
    """Tests for admin endpoints."""
    
    def test_create_model_success(self, client, authenticated_user):
        """Test creating model via API."""
        response = client.post(
            "/admin/models",
            json={
                "code": "TEST01",
                "name": "Test Model",
                "allowed_sizes": ["P", "M", "G"],
            },
            headers={"Authorization": f"Bearer {authenticated_user.token}"},
        )
        
        assert response.status_code == 201
        assert response.json()["code"] == "TEST01"
    
    def test_create_model_duplicate_code(self, client, authenticated_user):
        """Test creating model with duplicate code."""
        # Create first
        client.post(
            "/admin/models",
            json={
                "code": "DUP01",
                "name": "First",
                "allowed_sizes": ["P"],
            },
        )
        
        # Create duplicate
        response = client.post(
            "/admin/models",
            json={
                "code": "DUP01",
                "name": "Second",
                "allowed_sizes": ["P"],
            },
        )
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    
    def test_list_models_respects_tenant(self, client, authenticated_user):
        """Test that models list is tenant-isolated."""
        # Should only see own tenant's models
        response = client.get("/admin/models")
        
        assert response.status_code == 200
        assert all(m["tenant_id"] == authenticated_user.tenant_id for m in response.json())
```

### E2E Tests - Wizard Flow

```python
# backend/tests/e2e/test_wizard_flow.py
@pytest.mark.asyncio
class TestWizardFlow:
    """End-to-end wizard flow tests."""
    
    async def test_complete_wizard_flow(self, client, authenticated_user, mock_bling_client):
        """Test complete wizard flow from start to plan execution."""
        
        # Step 1: Create models & colors
        client.post("/admin/models", json={...})
        client.post("/admin/colors", json={...})
        
        # Step 2: Start wizard
        wizard_response = client.post(
            "/wizard/new",
            json={
                "print_type": "DIGITAL",
                "models": ["MODELO01"],
                "colors": ["BRANCO"],
            },
        )
        assert wizard_response.status_code == 200
        plan_data = wizard_response.json()
        
        # Step 3: Add templates
        client.post(
            f"/plans/{plan_data['id']}/templates",
            json={...},
        )
        
        # Step 4: Execute plan
        exec_response = client.post(
            f"/plans/{plan_data['id']}/execute",
        )
        assert exec_response.status_code == 200
        
        # Step 5: Verify execution result
        result = exec_response.json()
        assert result["status"] == "completed"
        assert result["summary"]["success"] > 0
```

---

## 🚀 Rodando Testes

### Todos os testes

```bash
pytest backend/tests/ -v
```

### Apenas unit tests

```bash
pytest backend/tests/unit/ -v
```

### Com cobertura

```bash
pytest backend/tests/ --cov=app --cov-report=html
# Abre htmlcov/index.html no browser
```

### Testes específicos

```bash
# Um arquivo
pytest backend/tests/unit/test_repositories.py -v

# Uma classe
pytest backend/tests/unit/test_repositories.py::TestModelRepository -v

# Um teste
pytest backend/tests/unit/test_repositories.py::TestModelRepository::test_create -v
```

### Modo watch (re-run on file change)

```bash
pytest-watch backend/tests/ -v
```

---

## ✅ Checklist de Cobertura

Áreas que precisam de testes (prioridade):

- [ ] **Repositories** (HIGH)
  - [ ] get_by_id
  - [ ] list_all
  - [ ] create
  - [ ] update
  - [ ] delete
  - [ ] Tenant isolation

- [ ] **Services** (HIGH)
  - [ ] PlanService.create
  - [ ] PlanService.execute
  - [ ] BlingService.sync

- [ ] **API Endpoints** (MEDIUM)
  - [ ] POST /admin/models
  - [ ] POST /admin/colors
  - [ ] POST /plans
  - [ ] POST /plans/execute

- [ ] **Helpers** (MEDIUM)
  - [ ] parse_color_and_size
  - [ ] extract_dependencies
  - [ ] _merge_variations

- [ ] **Auth** (LOW)
  - [ ] OAuth flow (mostly 3rd party)
  - [ ] Token refresh

---

## 🐛 Mocking Patterns

### Mock Bling API

```python
@pytest.fixture
def mock_bling_get_products(mock_bling_client):
    """Mock Bling products GET."""
    mock_bling_client.get.return_value = {
        "data": [
            {"id": 1, "codigo": "SKU001", "nome": "Product 1"},
        ]
    }
    return mock_bling_client

# Uso
async def test_something(mock_bling_get_products):
    result = await some_function()
    mock_bling_get_products.get.assert_called()
```

### Mock Database Query

```python
def test_with_mocked_query(mocker):
    """Mock SQLAlchemy query."""
    mock_query = mocker.MagicMock()
    mock_query.filter.return_value.first.return_value = sample_model
    
    mocker.patch.object(session, "query", return_value=mock_query)
```

---

## 📊 Cobertura Atual

Executar e gerar relatório:

```bash
pytest backend/tests/ --cov=app --cov-report=term-missing
```

Expected output:
```
Name                                Stmts   Miss  Cover
─────────────────────────────────────────────────────
app/repositories/base.py              120     15   87%
app/repositories/model_repo.py         60      8   87%
app/models/schemas.py                 200     30   85%
...
────────────────────────────────────────────────────
TOTAL                               2500    300   88%
```

---

## 🔄 CI/CD Integration

Adicionar ao GitHub Actions:

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
      redis:
        image: redis:7
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.10
      
      - run: pip install -r backend/requirements.txt pytest pytest-cov
      - run: pytest backend/tests/ --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## 📞 Próximos Passos

1. Implementar fixtures básicas (conftest.py)
2. Criar 5-10 testes de exemplo
3. Configurar GitHub Actions
4. Aumentar cobertura gradualmente para 80%+
