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
from app.api import auth, access_control, jobs, config_models, config_colors, config_templates, bling_products, plans, plan_execution, dashboard, events, orders
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
}


# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    
    logger.info("application_startup - version=%s, debug=%s", settings.VERSION, settings.DEBUG)
    
    yield
    
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

        if path in PUBLIC_PATHS or path.startswith("/auth/bling"):
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
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        return HealthResponse(
            status="healthy",
            version=settings.VERSION,
        )
    
    return app


app = create_app()
