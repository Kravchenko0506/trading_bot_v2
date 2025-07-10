# database/connection.py
"""
Database connection management with async support.
Handles SQLite for development, PostgreSQL for production.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base
from utils.logger import get_system_logger

logger = get_system_logger()

# Global variables
engine = None
SessionLocal = None


async def init_database(database_url: str = None):
    """
    Initialize database connection and create tables.
    Uses SQLite by default, PostgreSQL in production.
    """
    global engine, SessionLocal
    
    if database_url is None:
        # Default to SQLite for development
        db_path = os.path.join("data", "trading_bot.db")
        os.makedirs("data", exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_path}"
    
    # Create async engine
    if "sqlite" in database_url:
        # SQLite specific settings
        engine = create_async_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 20
            },
            echo=False  # Set to True for SQL debugging
        )
    else:
        # PostgreSQL settings
        engine = create_async_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            echo=False
        )
    
    # Create session factory
    SessionLocal = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info(f"Database initialized: {database_url}")


@asynccontextmanager
async def get_db_session():
    """
    Get database session with automatic cleanup.
    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
            await session.commit()
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with SessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def close_database():
    """Close database connection pool"""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


# Health check function
async def check_database_health() -> bool:
    """Check if database is accessible"""
    try:
        async with get_db_session() as session:
            result = await session.execute("SELECT 1")
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# Migration helper (basic)
async def run_migrations():
    """
    Run database migrations.
    For production, use Alembic instead.
    """
    try:
        async with engine.begin() as conn:
            # Drop all tables (development only!)
            await conn.run_sync(Base.metadata.drop_all)
            # Recreate all tables
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database migrations completed")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


# Utility function for raw SQL queries
async def execute_raw_sql(query: str, params: dict = None):
    """Execute raw SQL query (use sparingly)"""
    async with get_db_session() as session:
        result = await session.execute(query, params or {})
        await session.commit()
        return result