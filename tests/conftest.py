"""Pytest fixtures for testing."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text

from app.main import app
from app.common.database import Base, get_db
from app.common.config import settings
from app.common.rate_limit import limiter
from app.domain.auth_service import hash_password
from app.domain.token_service import create_token_info, calculate_expiry_date
from app.models.user import User
from app.models.token import Token


# Test database URL
TEST_DATABASE_URL = settings.database_url.replace("/pat_db", "/pat_test")


async def ensure_test_database_exists():
    """Ensure test database exists, create if it doesn't."""
    # Connect to postgres database to create pat_test database
    postgres_url = settings.database_url.replace("/pat_db", "/postgres")
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT", echo=False)

    async with engine.connect() as conn:
        # Check if database exists
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'pat_test'")
        )
        exists = result.scalar() is not None

        if not exists:
            # Create test database
            await conn.execute(text("CREATE DATABASE pat_test"))
            print("✓ Created test database: pat_test")

    await engine.dispose()


async def cleanup_test_database():
    """Drop test database after all tests complete."""
    # Connect to postgres database to drop pat_test database
    postgres_url = settings.database_url.replace("/pat_db", "/postgres")
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT", echo=False)

    async with engine.connect() as conn:
        # Terminate all connections to pat_test
        await conn.execute(
            text("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = 'pat_test'
                  AND pid <> pg_backend_pid()
            """)
        )

        # Drop test database
        await conn.execute(text("DROP DATABASE IF EXISTS pat_test"))
        print("✓ Cleaned up test database: pat_test")

    await engine.dispose()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database(event_loop):
    """Setup test database before any tests run, cleanup after all tests complete."""
    # Setup: Create test database
    await ensure_test_database_exists()

    yield

    # Teardown: Drop test database
    await cleanup_test_database()


@pytest.fixture(scope="function")
async def test_db():
    """Create test database and tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    # Override dependency
    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiting in tests
    limiter.enabled = False

    yield async_session_maker

    # Cleanup
    app.dependency_overrides.clear()

    # Ensure limiter is disabled
    limiter.enabled = False

    # Clear rate limit storage to prevent test pollution
    if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
        storage = limiter._limiter.storage
        # Clear all internal data structures
        if hasattr(storage, 'reset'):
            storage.reset()
        if hasattr(storage, 'storage'):
            storage.storage.clear()
        if hasattr(storage, 'expirations'):
            storage.expirations.clear()
        if hasattr(storage, 'events'):
            storage.events.clear()

    await engine.dispose()


@pytest.fixture
async def client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def rate_limit_test():
    """Fixture for rate limiting tests that ensures clean storage."""
    from app.common.rate_limit import limiter

    # Save original state
    original_enabled = limiter.enabled

    # Enable limiter for rate limit tests
    limiter.enabled = True

    # Clear storage before test
    if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
        storage = limiter._limiter.storage
        if hasattr(storage, 'reset'):
            storage.reset()
        if hasattr(storage, 'storage'):
            storage.storage.clear()
        if hasattr(storage, 'expirations'):
            storage.expirations.clear()
        if hasattr(storage, 'events'):
            storage.events.clear()

    yield limiter

    # Restore state and clear storage after test
    limiter.enabled = original_enabled

    if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
        storage = limiter._limiter.storage
        if hasattr(storage, 'reset'):
            storage.reset()
        if hasattr(storage, 'storage'):
            storage.storage.clear()
        if hasattr(storage, 'expirations'):
            storage.expirations.clear()
        if hasattr(storage, 'events'):
            storage.events.clear()


@pytest.fixture
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_db() as session:
        yield session


@pytest.fixture
async def user_a(session: AsyncSession) -> User:
    """Create test user A."""
    user = User(
        username="user_a",
        email="user_a@example.com",
        password_hash=hash_password("password123"),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def user_b(session: AsyncSession) -> User:
    """Create test user B."""
    user = User(
        username="user_b",
        email="user_b@example.com",
        password_hash=hash_password("password123"),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def user_a_jwt(client: AsyncClient, user_a: User) -> str:
    """Get JWT token for user A."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "user_a", "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.fixture
async def user_b_jwt(client: AsyncClient, user_b: User) -> str:
    """Get JWT token for user B."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "user_b", "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.fixture
async def create_pat_token(session: AsyncSession):
    """Factory to create PAT tokens."""
    async def _create_token(
        user_id,
        scopes: list[str],
        name: str = "Test Token",
        expires_in_days: int = 30,
        is_revoked: bool = False,
    ) -> tuple[str, Token]:
        """Create a PAT token and return (full_token, token_model)."""
        token_info = create_token_info()
        expires_at = calculate_expiry_date(expires_in_days)

        token = Token(
            user_id=user_id,
            name=name,
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=scopes,
            expires_at=expires_at,
            is_revoked=is_revoked,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
        return token_info.full_token, token

    return _create_token


@pytest.fixture
async def expired_token(session: AsyncSession, user_a: User, create_pat_token):
    """Create an expired PAT token."""
    # Create token that expired 1 day ago
    token_info = create_token_info()
    expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    token = Token(
        user_id=user_a.id,
        name="Expired Token",
        token_hash=token_info.token_hash,
        token_prefix=token_info.token_prefix,
        scopes=["workspacess:read"],
        expires_at=expires_at,
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token_info.full_token, token
