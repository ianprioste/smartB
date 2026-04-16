"""FastAPI application factory and setup."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid

from app.settings import settings
from app.infra.logging import get_logger, RequestIdMiddleware
from app.models.database import Base
from app.infra.db import engine, SessionLocal
from app.models.schemas import HealthResponse
from app.api import auth, access_control, jobs, config_models, config_colors, config_templates, bling_products, plans, plan_execution, dashboard, events, orders, webhooks
from app.repositories.access_repo import AccessRepository

logger = get_logger(__name__)

SESSION_COOKIE = "smartb_session"
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/access/login",
    "/auth/access/bootstrap-status",
    "/auth/access/forgot-password/request",
    "/auth/access/forgot-password/verify",
    "/auth/access/forgot-password/reset",
    "/webhooks/health",
}
# Webhook paths are authenticated by shared secret, not by session cookie.
WEBHOOK_PATH_PREFIXES = {"/webhooks/bling/"}


# Create database tables
Base.metadata.create_all(bind=engine)

# Ensure critical columns exist on SQLite (handles cases where
# Alembic migrations fail but create_all built the table without them).
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import text as _text, inspect as _sa_inspect
    with engine.connect() as _conn:
        _cols = {c["name"] for c in _sa_inspect(engine).get_columns("bling_order_snapshots")}
        if "customer_email" not in _cols:
            _conn.execute(_text("ALTER TABLE bling_order_snapshots ADD COLUMN customer_email VARCHAR(500)"))
            _conn.commit()
        if "customer_contact_id" not in _cols:
            _conn.execute(_text("ALTER TABLE bling_order_snapshots ADD COLUMN customer_contact_id BIGINT"))
            _conn.commit()

# Ensure default tenant exists
def _ensure_default_tenant():
    from app.models.database import TenantModel
    _default_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    db = SessionLocal()
    try:
        existing = db.query(TenantModel).filter(TenantModel.id == _default_id).first()
        if not existing:
            db.add(TenantModel(id=_default_id, name="Default"))
            db.commit()
            logger.info("Default tenant created (id=%s)", _default_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

_ensure_default_tenant()


_incremental_sync_stop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    global _incremental_sync_stop
    
    logger.info("application_startup - version=%s, debug=%s", settings.VERSION, settings.DEBUG)

    # Start periodic incremental sync (every N minutes, without Celery)
    import threading, time as _time
    interval = getattr(settings, "ORDERS_INCREMENTAL_SYNC_MINUTES", 15) * 60
    stop_event = threading.Event()
    _incremental_sync_stop = stop_event

    def _periodic_incremental_sync():
        # Wait one full interval before first run
        if stop_event.wait(timeout=interval):
            return
        while not stop_event.is_set():
            try:
                from app.api.orders import _run_sync_in_local_background
                logger.info("periodic_incremental_sync_triggered")
                _run_sync_in_local_background("incremental")
            except Exception as exc:
                logger.warning("periodic_incremental_sync_error error=%s", str(exc))
            if stop_event.wait(timeout=interval):
                return

    t = threading.Thread(target=_periodic_incremental_sync, daemon=True)
    t.start()
    
    yield
    
    stop_event.set()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request ID middleware
    app.add_middleware(RequestIdMiddleware)

    @app.middleware("http")
    async def access_guard(request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS or path.startswith("/auth/bling") or any(path.startswith(p) for p in WEBHOOK_PATH_PREFIXES):
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Não autenticado"})

        db = SessionLocal()
        try:
            user = AccessRepository.get_session_user(db, token)
            if not user:
                return JSONResponse(status_code=401, content={"detail": "Sessão inválida"})
            request.state.access_user = user
        finally:
            db.close()

        return await call_next(request)
    
    # Include routers
    app.include_router(auth.router)
    app.include_router(access_control.router)
    app.include_router(jobs.router)
    app.include_router(config_models.router)
    app.include_router(config_colors.router)
    app.include_router(config_templates.router)
    app.include_router(bling_products.router)
    app.include_router(plans.router)
    app.include_router(plan_execution.router)
    app.include_router(dashboard.router)
    app.include_router(events.router)
    app.include_router(orders.router)
    app.include_router(webhooks.router)
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=settings.VERSION,
            git_commit=settings.GIT_COMMIT,
            build_id=settings.BUILD_ID,
            build_timestamp=settings.BUILD_TIMESTAMP,
        )
    
    return app


app = create_app()
