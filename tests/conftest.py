"""Pytest fixtures for testing."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.common.database import Base, get_db
from app.common.config import settings
from app.domain.auth_service import hash_password
from app.domain.token_service import create_token_info, calculate_expiry_date
from app.models.user import User
from app.models.token import Token


# Test database URL
TEST_DATABASE_URL = settings.database_url.replace("/pat", "/pat_test")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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

    yield async_session_maker

    # Cleanup
    app.dependency_overrides.clear()
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
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_db() as session:
        yield session


@pytest.fixture
async def user_a(session: AsyncSession) -> User:
    """Create test user A."""
    async with session.begin():
        user = User(
            username="user_a",
            email="user_a@example.com",
            password_hash=hash_password("password123"),
        )
        session.add(user)

    await session.refresh(user)
    return user


@pytest.fixture
async def user_b(session: AsyncSession) -> User:
    """Create test user B."""
    async with session.begin():
        user = User(
            username="user_b",
            email="user_b@example.com",
            password_hash=hash_password("password123"),
        )
        session.add(user)

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

        async with session.begin():
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

        await session.refresh(token)
        return token_info.full_token, token

    return _create_token


@pytest.fixture
async def expired_token(session: AsyncSession, user_a: User, create_pat_token):
    """Create an expired PAT token."""
    # Create token that expired 1 day ago
    token_info = create_token_info()
    expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    async with session.begin():
        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspaces:read"],
            expires_at=expires_at,
        )
        session.add(token)

    await session.refresh(token)
    return token_info.full_token, token
