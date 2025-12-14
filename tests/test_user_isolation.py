"""Test user isolation.

Test cases:
- User A cannot see User B's data
- User A cannot access User B's tokens
- User A cannot revoke User B's tokens
"""
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.isolation
class TestUserIsolation:
    """Test that users cannot access each other's data."""

    async def test_user_a_cannot_list_user_b_tokens(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, user_b_jwt: str, create_pat_token
    ):
        """Test that User A cannot see User B's tokens."""
        # Create tokens for both users
        _, token_a = await create_pat_token(user_a.id, scopes=["workspacess:read"], name="Token A")
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"], name="Token B")

        # User A lists their tokens
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["tokens"][0]["name"] == "Token A"

        # User B lists their tokens
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_b_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["tokens"][0]["name"] == "Token B"

    async def test_user_a_cannot_get_user_b_token_details(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test that User A cannot get details of User B's token."""
        # Create token for User B
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"], name="Token B")

        # User A tries to get User B's token details
        response = await client.get(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Forbidden"
        assert "Access denied" in response.json()["message"]

    async def test_user_a_cannot_revoke_user_b_token(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test that User A cannot revoke User B's token."""
        # Create token for User B
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"], name="Token B")

        # User A tries to revoke User B's token
        response = await client.delete(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Forbidden"

    async def test_user_a_cannot_view_user_b_token_logs(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test that User A cannot view User B's token audit logs."""
        # Create token for User B
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"], name="Token B")

        # User A tries to view User B's token logs
        response = await client.get(
            f"/api/v1/tokens/{token_b.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Forbidden"

    async def test_user_can_only_access_own_tokens(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, user_b_jwt: str, create_pat_token
    ):
        """Test that users can only access their own tokens."""
        # Create tokens for both users
        _, token_a = await create_pat_token(user_a.id, scopes=["workspacess:read"], name="Token A")
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"], name="Token B")

        # User A can access their own token
        response = await client.get(
            f"/api/v1/tokens/{token_a.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Token A"

        # User B can access their own token
        response = await client.get(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_b_jwt}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Token B"

        # User A cannot access User B's token
        response = await client.get(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403

        # User B cannot access User A's token
        response = await client.get(
            f"/api/v1/tokens/{token_a.id}",
            headers={"Authorization": f"Bearer {user_b_jwt}"}
        )
        assert response.status_code == 403
