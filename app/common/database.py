from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.common.config import settings

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions.

    Note: Each usecase is responsible for committing its transactions.
    This only handles rollback for uncaught exceptions.
    """
    async with async_session_maker() as session:
        try:
            yield session
            # Usecase is responsible for commit
            # Don't auto-commit here
        except Exception:
            # Rollback on uncaught exceptions
            await session.rollback()
            raise
        finally:
            # Close session (also done by context manager, but explicit is better)
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
