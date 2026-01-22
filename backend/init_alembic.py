"""Alembic migration initialization script."""
import os
from alembic.config import Config
from alembic.command import init as alembic_init
from app.settings import settings

def init_alembic():
    """Initialize Alembic for database migrations."""
    
    alembic_dir = "alembic"
    
    if not os.path.exists(alembic_dir):
        config = Config()
        config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        config.set_main_option("script_location", alembic_dir)
        
        alembic_init(config, alembic_dir)
        
        print(f"Alembic initialized in {alembic_dir}")
    else:
        print(f"{alembic_dir} already exists")

if __name__ == "__main__":
    init_alembic()
