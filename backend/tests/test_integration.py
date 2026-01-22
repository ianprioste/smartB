"""Basic integration tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.infra.db import get_db, SessionLocal
from app.models.database import Base, TenantModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Use in-memory SQLite for tests
# SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )

# For now, use test PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/smartbling_test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_get_bling_auth_url():
    """Test OAuth2 authorization URL generation."""
    response = client.post("/auth/bling/connect")
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "bling.com.br/oauth/authorize" in data["authorization_url"]


def test_create_job():
    """Test job creation."""
    payload = {
        "type": "sync_products",
        "input_payload": {"action": "full_sync"},
        "metadata": {"source": "test"},
    }
    
    response = client.post("/jobs", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["type"] == "sync_products"
    assert data["status"] == "QUEUED"
    assert "id" in data
    assert "created_at" in data


def test_get_job():
    """Test job retrieval."""
    # Create job
    payload = {
        "type": "sync_products",
        "input_payload": {"action": "full_sync"},
    }
    
    create_response = client.post("/jobs", json=payload)
    job_id = create_response.json()["id"]
    
    # Get job
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    
    assert data["id"] == job_id
    assert data["type"] == "sync_products"


def test_get_job_detail():
    """Test job detail with items."""
    # Create job
    payload = {
        "type": "test_job",
        "input_payload": {"test": True},
    }
    
    create_response = client.post("/jobs", json=payload)
    job_id = create_response.json()["id"]
    
    # Get detail
    detail_response = client.get(f"/jobs/{job_id}/detail")
    assert detail_response.status_code == 200
    data = detail_response.json()
    
    assert data["id"] == job_id
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_job_items():
    """Test job items retrieval."""
    # Create job
    payload = {
        "type": "test_job",
    }
    
    create_response = client.post("/jobs", json=payload)
    job_id = create_response.json()["id"]
    
    # Get items
    items_response = client.get(f"/jobs/{job_id}/items")
    assert items_response.status_code == 200
    items = items_response.json()
    
    assert isinstance(items, list)


def test_get_nonexistent_job():
    """Test retrieval of non-existent job."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/jobs/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
