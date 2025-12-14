"""Test token security and storage.

Test cases:
- Created PAT is not stored in plaintext in DB (only hash and prefix)
- Valid token with correct permissions returns 200
- Invalid token returns 401
- Prefix token cannot be used for authentication (returns 401)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.token import Token


@pytest.mark.security
class TestTokenStorage:
    """Test that tokens are stored securely."""

    async def test_token_not_stored_in_plaintext(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, user_a_jwt: str
    ):
        """Test that PAT full token is not stored in database."""
        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Security Test Token",
                "scopes": ["workspaces:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        full_token = data["token"]
        token_id = data["id"]

        # Verify token format (should start with pat_)
        assert full_token.startswith("pat_")

        # Check database - should have hash and prefix, but not full token
        result = await session.execute(
            select(Token).where(Token.id == token_id)
        )
        token_in_db = result.scalar_one()

        # Should have token_hash (not plaintext)
        assert token_in_db.token_hash is not None
        assert len(token_in_db.token_hash) > 0
        assert token_in_db.token_hash != full_token

        # Should have token_prefix
        assert token_in_db.token_prefix is not None
        assert full_token.startswith(token_in_db.token_prefix)

        # Verify no column contains the full token
        assert full_token != token_in_db.token_hash
        assert full_token != token_in_db.token_prefix
        assert full_token not in str(token_in_db.name)

    async def test_token_hash_is_consistent(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, user_a_jwt: str
    ):
        """Test that same token produces same hash."""
        from app.domain.token_service import hash_token

        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Hash Test Token",
                "scopes": ["workspaces:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        full_token = response.json()["data"]["token"]

        # Hash the token
        hash1 = hash_token(full_token)
        hash2 = hash_token(full_token)

        # Same token should produce same hash
        assert hash1 == hash2

        # Different tokens should produce different hashes
        different_token = full_token + "different"
        hash3 = hash_token(different_token)
        assert hash1 != hash3


@pytest.mark.security
class TestTokenAuthentication:
    """Test token authentication scenarios."""

    async def test_valid_token_with_permission_returns_200(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that valid token with correct permission works."""
        # Create token with workspaces:read permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspaces:read"]
        )

        # Should successfully access resource
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that invalid token returns 401."""
        # Use completely invalid token
        invalid_token = "pat_invalid_token_1234567890"

        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "InvalidToken"

    async def test_malformed_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that malformed token returns 401."""
        # Use malformed token (not starting with pat_)
        malformed_token = "not_a_valid_token"

        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "InvalidToken"

    async def test_prefix_token_cannot_authenticate(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, user_a_jwt: str
    ):
        """Test that prefix token cannot be used for authentication."""
        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Prefix Test Token",
                "scopes": ["workspaces:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        token_prefix = data["token_prefix"]

        # Try to use prefix token for authentication
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {token_prefix}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "InvalidToken"

    async def test_missing_authorization_header_returns_401(
        self, client: AsyncClient
    ):
        """Test that missing authorization header returns 401."""
        response = await client.get("/api/v1/workspaces")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_invalid_authorization_header_format_returns_401(
        self, client: AsyncClient
    ):
        """Test that invalid authorization header format returns 401."""
        # Missing "Bearer" prefix
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "pat_token123"}
        )
        assert response.status_code == 401

        # Wrong prefix
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Basic pat_token123"}
        )
        assert response.status_code == 401

    async def test_empty_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that empty token returns 401."""
        response = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code == 401
