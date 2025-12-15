"""Test users API endpoints.

Covers:
- GET /api/v1/users/me
- PUT /api/v1/users/me

All these endpoints require PAT authentication (stub implementation).
No 404 tests - these are stub APIs.

Status codes tested:
- 200 OK
- 401 Unauthorized (no auth, invalid token, expired token, revoked token)
- 403 Forbidden
"""
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.integration
class TestGetCurrentUser:
    """Test GET /api/v1/users/me endpoint."""

    async def test_get_current_user_200_with_read_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting current user with users:read permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["users:read"])

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_get_current_user_401_no_authorization_header(self, client: AsyncClient):
        """Test getting current user without Authorization header returns 401."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_get_current_user_401_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid PAT token returns 401."""
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer pat_invalid_token"}
        )
        assert response.status_code == 401

    async def test_get_current_user_401_expired_token(
        self, client: AsyncClient, session, user_a: User
    ):
        """Test getting current user with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["users:read"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401

    async def test_get_current_user_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting current user with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["users:read"],
            is_revoked=True
        )

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

    async def test_get_current_user_403_without_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting current user without users:read permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "users:read"
        assert data["data"]["your_scopes"] == ["workspacess:read"]


@pytest.mark.integration
class TestUpdateCurrentUser:
    """Test PUT /api/v1/users/me endpoint."""

    async def test_update_current_user_200_with_write_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating current user with users:write permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["users:write"])

        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_update_current_user_401_no_authorization_header(self, client: AsyncClient):
        """Test updating current user without Authorization header returns 401."""
        response = await client.put("/api/v1/users/me")
        assert response.status_code == 401

    async def test_update_current_user_401_invalid_token(self, client: AsyncClient):
        """Test updating current user with invalid PAT token returns 401."""
        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer pat_invalid"}
        )
        assert response.status_code == 401

    async def test_update_current_user_401_expired_token(
        self, client: AsyncClient, session, user_a: User
    ):
        """Test updating current user with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["users:write"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401

    async def test_update_current_user_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating current user with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["users:write"],
            is_revoked=True
        )

        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

    async def test_update_current_user_403_read_only_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating current user with only users:read permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["users:read"])

        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "users:write"
        assert data["data"]["your_scopes"] == ["users:read"]
