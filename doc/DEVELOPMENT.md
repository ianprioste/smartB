# smartBling v2 - Backend Development Notes

## Architecture Overview

### Layers

1. **API Layer** (`app/api/`)
   - FastAPI endpoints
   - Request/response handling
   - OAuth2 flows

2. **Domain Layer** (`app/domain/`)
   - Business logic (empty in Sprint 1)
   - Will contain product rules, SKU logic, etc

3. **Infrastructure Layer** (`app/infra/`)
   - Database connections
   - Redis client
   - Bling API client
   - Logging setup

4. **Models** (`app/models/`)
   - SQLAlchemy ORM (database.py)
   - Pydantic schemas (schemas.py)

5. **Repositories** (`app/repositories/`)
   - Data access layer
   - Database queries
   - Encapsulation of CRUD operations

6. **Workers** (`app/workers/`)
   - Celery configuration
   - Async task definitions

## Key Design Decisions

### 1. Single Tenant (for now)
Sprint 1 uses a fixed default tenant UUID. Multi-tenant support is
prepared but not fully utilized yet.

### 2. Token Storage
Tokens are stored in plain text (TODO: encryption in production).
Never log tokens - they're masked in logs.

### 3. Job Model
Jobs can contain multiple items, allowing batch processing:
- Job: represents a batch operation
- JobItems: individual items within the batch

### 4. Structured Logging
All logs are JSON-formatted for easier parsing and monitoring.
Each request has a unique request_id for tracing.

### 5. Retry Strategy
BlingClient uses exponential backoff for:
- Rate limiting (429)
- Server errors (5xx)
Automatic token refresh on 401

## Future Considerations (Sprint 2+)

### Database
- Add indexes for common queries
- Consider partitioning for large datasets
- Archive old jobs after 30 days

### API
- Add authentication (JWT or similar)
- Implement rate limiting
- Add request validation middleware

### Workers
- Add job priorities
- Implement job dependencies
- Add monitoring/alerting

### Bling Integration
- Handle webhook events from Bling
- Implement polling for status changes
- Add transaction logging

## Development Workflow

1. Create migration in `alembic/versions/`
2. Define ORM model in `app/models/database.py`
3. Create schema in `app/models/schemas.py`
4. Implement repository in `app/repositories/`
5. Create API endpoint in `app/api/`
6. Add task to `app/workers/tasks.py` if async
7. Add logging events

## Testing Strategy

- Unit tests for repositories
- Integration tests for APIs
- End-to-end tests for OAuth2 flow
- Load tests for worker processing

## Deployment

- Use environment variables for config
- Run migrations on startup
- Scale workers independently
- Monitor logs in production

---

Last Updated: 21/01/2025
