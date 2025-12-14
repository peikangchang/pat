"""Test token expiration and revocation.

Test cases:
- Expired token returns 401 with "TokenExpired" error
- Revoked token returns 401 with "TokenRevoked" error
- Valid token works correctly
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.domain.token_service import create_token_info
from app.models.token import Token
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.unit
class TestTokenExpiration:
    """Test token expiration handling."""

    async def test_expired_token_returns_401(
        self, client: AsyncClient, session: AsyncSession, user_a: User
    ):
        """Test that expired token returns 401 with TokenExpired error."""
        # Create expired token (expired 1 day ago)
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

        # Try to use expired token
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "TokenExpired"
        assert "expired" in response.json()["message"].lower()

    async def test_almost_expired_token_still_works(
        self, client: AsyncClient, session: AsyncSession, user_a: User
    ):
        """Test that token expiring soon still works."""
        # Create token expiring in 1 hour
        token_info = create_token_info()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = Token(
            user_id=user_a.id,
            name="Almost Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspacess:read"],
            expires_at=expires_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        # Should still work
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 200


@pytest.mark.unit
class TestTokenRevocation:
    """Test token revocation handling."""

    async def test_revoked_token_returns_401(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that revoked token returns 401 with TokenRevoked error."""
        # Create token
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"], name="To Be Revoked"
        )

        # Verify token works
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Revoke token
        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_revoked"] is True

        # Try to use revoked token
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "TokenRevoked"
        assert "revoked" in response.json()["message"].lower()

    async def test_cannot_revoke_already_revoked_token(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that revoking an already revoked token still succeeds (idempotent)."""
        # Create token
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"], name="To Be Revoked"
        )

        # Revoke token first time
        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200

        # Revoke token second time (should still succeed)
        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_revoked"] is True

    async def test_revoked_token_appears_in_token_list(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that revoked tokens still appear in token list."""
        # Create and revoke token
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"], name="Revoked Token"
        )

        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200

        # List tokens
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        tokens = response.json()["data"]["tokens"]
        assert len(tokens) == 1
        assert tokens[0]["is_revoked"] is True
        assert tokens[0]["name"] == "Revoked Token"


@pytest.mark.unit
class TestValidToken:
    """Test that valid tokens work correctly."""

    async def test_valid_token_with_correct_permissions(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that valid token with correct permissions returns 200."""
        # Create token with workspacess:read permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Should work
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_valid_token_without_required_permission_returns_403(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that valid token without required permission returns 403."""
        # Create token with only read permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Try to write (requires workspacess:write)
        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:write"
        assert data["data"]["your_scopes"] == ["workspacess:read"]
