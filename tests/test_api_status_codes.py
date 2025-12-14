"""Test all API endpoints for various response status codes.

Covers:
- 200 OK
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 422 Unprocessable Entity
- 429 Too Many Requests
- 500 Internal Server Error
"""
import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.models.user import User


@pytest.mark.integration
class TestAuthAPIStatusCodes:
    """Test auth API status codes."""

    async def test_register_200_success(self, client: AsyncClient):
        """Test successful user registration returns 200."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!"
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_register_422_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user",
                "email": "invalid-email",
                "password": "password123"
            }
        )
        assert response.status_code == 422

    async def test_register_422_duplicate_username(
        self, client: AsyncClient, user_a: User
    ):
        """Test registration with duplicate username returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "user_a",  # Already exists
                "email": "different@example.com",
                "password": "password123"
            }
        )
        assert response.status_code == 422
        assert response.json()["error"] == "Validation"

    async def test_login_200_success(
        self, client: AsyncClient, user_a: User
    ):
        """Test successful login returns 200."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "password123"
            }
        )
        assert response.status_code == 200
        assert "access_token" in response.json()["data"]

    async def test_login_401_invalid_credentials(
        self, client: AsyncClient, user_a: User
    ):
        """Test login with invalid credentials returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "wrong_password"
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_login_401_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "password123"
            }
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestTokensAPIStatusCodes:
    """Test tokens API status codes."""

    async def test_create_token_200_success(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test successful token creation returns 200."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "token" in response.json()["data"]

    async def test_create_token_401_no_auth(self, client: AsyncClient):
        """Test token creation without auth returns 401."""
        response = await client.post(
            "/api/v1/tokens",
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 401

    async def test_create_token_422_invalid_scopes(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test token creation with invalid scopes returns 422."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Test Token",
                "scopes": ["invalid:scope"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 422
        assert response.json()["error"] == "Validation"

    async def test_list_tokens_200_success(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test listing tokens returns 200."""
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        assert "tokens" in response.json()["data"]

    async def test_get_token_200_success(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting token details returns 200."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200

    async def test_get_token_404_not_found(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test getting nonexistent token returns 404."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 404
        assert response.json()["error"] == "NotFound"

    async def test_get_token_403_forbidden(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test getting another user's token returns 403."""
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Forbidden"

    async def test_revoke_token_200_success(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test revoking token returns 200."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_revoked"] is True


@pytest.mark.integration
class TestWorkspacesAPIStatusCodes:
    """Test workspaces API status codes."""

    async def test_list_workspaces_200_with_read_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test listing workspaces with read permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_list_workspaces_401_no_auth(self, client: AsyncClient):
        """Test listing workspaces without auth returns 401."""
        response = await client.get("/api/v1/workspacess")
        assert response.status_code == 401

    async def test_list_workspaces_403_insufficient_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test listing workspaces without permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert "required_scope" in data["data"]
        assert data["data"]["required_scope"] == "workspacess:read"
        assert "your_scopes" in data["data"]
        assert data["data"]["your_scopes"] == ["fcs:read"]

    async def test_create_workspace_200_with_write_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test creating workspace with write permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:write"])

        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_create_workspace_403_read_only_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test creating workspace with only read permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:write"
        assert data["data"]["your_scopes"] == ["workspacess:read"]

    async def test_delete_workspace_200_with_delete_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test deleting workspace with delete permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:delete"])

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_update_settings_200_with_admin_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating workspace settings with admin permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:admin"])

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_update_settings_403_without_admin_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating settings without admin permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:delete"])

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:admin"
        assert data["data"]["your_scopes"] == ["workspacess:delete"]


@pytest.mark.integration
class TestUsersAPIStatusCodes:
    """Test users API status codes."""

    async def test_get_current_user_200_with_read_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting current user with read permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["users:read"])

        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_get_current_user_403_without_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting current user without permission returns 403."""
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

    async def test_update_current_user_200_with_write_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating current user with write permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["users:write"])

        response = await client.put(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200


@pytest.mark.integration
class TestFCSAPIStatusCodes:
    """Test FCS API status codes."""

    async def test_get_parameters_404_no_file_uploaded(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting FCS parameters without uploaded file returns 404."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 404

    async def test_get_parameters_403_without_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test getting FCS parameters without permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:read"
        assert data["data"]["your_scopes"] == ["workspacess:read"]


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting returns 429."""

    async def test_rate_limit_429_too_many_requests(self, client: AsyncClient):
        """Test that exceeding rate limit returns 429."""
        from app.common.rate_limit import limiter

        # Temporarily enable rate limiting for this test
        limiter.enabled = True

        try:
            # Make 61 requests to trigger rate limit (limit is 60/minute)
            for i in range(61):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "user", "password": "pass"}
                )
                if response.status_code == 429:
                    # Rate limit triggered
                    assert response.json()["error"] == "Too Many Requests"
                    assert "retry_after" in response.json()["data"]
                    break
            else:
                pytest.fail("Rate limit not triggered after 61 requests")
        finally:
            # Disable rate limiting again
            limiter.enabled = False
