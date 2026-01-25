"""FastAPI application factory and setup."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid

from app.settings import settings
from app.infra.logging import get_logger, RequestIdMiddleware
from app.models.database import Base
from app.infra.db import engine
from app.models.schemas import HealthResponse
from app.api import auth, jobs, config_models, config_colors, config_templates, bling_products, plans, plan_execution

logger = get_logger(__name__)


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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request ID middleware
    app.add_middleware(RequestIdMiddleware)
    
    # Include routers
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(config_models.router)
    app.include_router(config_colors.router)
    app.include_router(config_templates.router)
    app.include_router(bling_products.router)
    app.include_router(plans.router)
    app.include_router(plan_execution.router)
    
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
