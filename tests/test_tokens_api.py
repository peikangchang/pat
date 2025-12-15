"""Test PAT token management API endpoints.

Covers:
- POST /api/v1/tokens
- GET /api/v1/tokens
- GET /api/v1/tokens/{token_id}
- DELETE /api/v1/tokens/{token_id}
- GET /api/v1/tokens/{token_id}/logs

All these endpoints require JWT authentication.

Status codes tested:
- 200 OK
- 401 Unauthorized (no auth, invalid JWT, expired JWT)
- 403 Forbidden
- 404 Not Found
- 422 Unprocessable Entity
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from httpx import AsyncClient

from app.models.user import User
from app.models.token import Token


@pytest.mark.integration
class TestCreateToken:
    """Test POST /api/v1/tokens endpoint."""

    async def test_create_token_200_success(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test successful token creation returns 200 with full token."""
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
        data = response.json()["data"]

        # Should return full token (only time it's shown)
        assert "token" in data
        assert data["token"].startswith("pat_")
        assert len(data["token"]) > 12  # pat_ + at least 8 chars

        # Should also return token details
        assert "id" in data
        assert data["name"] == "Test Token"
        assert data["scopes"] == ["workspacess:read"]
        assert "expires_at" in data
        assert "created_at" in data

    async def test_create_token_401_no_authorization_header(
        self, client: AsyncClient
    ):
        """Test token creation without Authorization header returns 401."""
        response = await client.post(
            "/api/v1/tokens",
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_create_token_401_invalid_jwt(self, client: AsyncClient):
        """Test token creation with invalid JWT returns 401."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": "Bearer invalid_jwt_token"},
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_create_token_401_expired_jwt(self, client: AsyncClient, user_a: User):
        """Test token creation with expired JWT returns 401."""
        # Create an expired JWT token
        from app.domain.auth_service import create_access_token

        expired_jwt = create_access_token(
            user_id=user_a.id,
            expires_delta=timedelta(seconds=-1)  # Already expired
        )

        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {expired_jwt}"},
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

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

    async def test_create_token_422_expires_out_of_range(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test token creation with expires_in_days > 365 returns 422."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 400  # More than 365
            }
        )
        assert response.status_code == 422

    async def test_create_token_422_negative_expires(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test token creation with negative expires_in_days returns 422."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": -10
            }
        )
        assert response.status_code == 422

    async def test_create_token_422_missing_name(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test token creation without name returns 422."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 422

    async def test_create_token_422_missing_scopes(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test token creation without scopes returns 422."""
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Test Token",
                "expires_in_days": 30
            }
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestListTokens:
    """Test GET /api/v1/tokens endpoint."""

    async def test_list_tokens_200_success(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test listing tokens returns 200 with token list (prefix only)."""
        # Create some tokens
        await create_pat_token(user_a.id, scopes=["workspacess:read"], name="Token 1")
        await create_pat_token(user_a.id, scopes=["fcs:read"], name="Token 2")

        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "tokens" in data
        assert len(data["tokens"]) >= 2

        # Should only show prefix, not full token
        for token in data["tokens"]:
            assert "token_prefix" in token
            assert token["token_prefix"].startswith("pat_")
            assert len(token["token_prefix"]) == 12  # pat_ + 8 chars
            assert "token" not in token  # Full token should not be exposed

    async def test_list_tokens_401_no_authorization_header(
        self, client: AsyncClient
    ):
        """Test listing tokens without Authorization header returns 401."""
        response = await client.get("/api/v1/tokens")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_list_tokens_401_invalid_jwt(self, client: AsyncClient):
        """Test listing tokens with invalid JWT returns 401."""
        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": "Bearer invalid_jwt_token"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_list_tokens_401_expired_jwt(self, client: AsyncClient, user_a: User):
        """Test listing tokens with expired JWT returns 401."""
        from app.domain.auth_service import create_access_token

        expired_jwt = create_access_token(
            user_id=user_a.id,
            expires_delta=timedelta(seconds=-1)
        )

        response = await client.get(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {expired_jwt}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"


@pytest.mark.integration
class TestGetToken:
    """Test GET /api/v1/tokens/{token_id} endpoint."""

    async def test_get_token_200_success(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting token details returns 200 (prefix only)."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]

        # Should only show prefix, not full token
        assert "token_prefix" in data
        assert data["token_prefix"].startswith("pat_")
        assert "token" not in data  # Full token should not be exposed
        assert data["id"] == str(token.id)

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

    async def test_get_token_401_no_authorization_header(
        self, client: AsyncClient
    ):
        """Test getting token without Authorization header returns 401."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/tokens/{fake_id}")
        assert response.status_code == 401

    async def test_get_token_401_invalid_jwt(self, client: AsyncClient):
        """Test getting token with invalid JWT returns 401."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": "Bearer invalid_jwt"}
        )
        assert response.status_code == 401

    async def test_get_token_401_expired_jwt(self, client: AsyncClient, user_a: User):
        """Test getting token with expired JWT returns 401."""
        from app.domain.auth_service import create_access_token

        expired_jwt = create_access_token(
            user_id=user_a.id,
            expires_delta=timedelta(seconds=-1)
        )
        fake_id = uuid4()

        response = await client.get(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": f"Bearer {expired_jwt}"}
        )
        assert response.status_code == 401

    async def test_get_token_422_invalid_uuid_format(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test getting token with invalid UUID format returns 422."""
        response = await client.get(
            "/api/v1/tokens/not-a-uuid",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestRevokeToken:
    """Test DELETE /api/v1/tokens/{token_id} endpoint."""

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
        data = response.json()["data"]
        assert data["is_revoked"] is True

    async def test_revoke_token_200_idempotent(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test revoking already revoked token returns 200 (idempotent)."""
        _, token = await create_pat_token(
            user_a.id,
            scopes=["workspacess:read"],
            is_revoked=True  # Already revoked
        )

        response = await client.delete(
            f"/api/v1/tokens/{token.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_revoked"] is True

    async def test_revoke_token_404_not_found(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test revoking nonexistent token returns 404."""
        fake_id = uuid4()
        response = await client.delete(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 404

    async def test_revoke_token_403_forbidden(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test revoking another user's token returns 403."""
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"])

        response = await client.delete(
            f"/api/v1/tokens/{token_b.id}",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403

    async def test_revoke_token_401_no_authorization_header(
        self, client: AsyncClient
    ):
        """Test revoking token without Authorization header returns 401."""
        fake_id = uuid4()
        response = await client.delete(f"/api/v1/tokens/{fake_id}")
        assert response.status_code == 401

    async def test_revoke_token_401_invalid_jwt(self, client: AsyncClient):
        """Test revoking token with invalid JWT returns 401."""
        fake_id = uuid4()
        response = await client.delete(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": "Bearer invalid_jwt"}
        )
        assert response.status_code == 401

    async def test_revoke_token_401_expired_jwt(self, client: AsyncClient, user_a: User):
        """Test revoking token with expired JWT returns 401."""
        from app.domain.auth_service import create_access_token

        expired_jwt = create_access_token(
            user_id=user_a.id,
            expires_delta=timedelta(seconds=-1)
        )
        fake_id = uuid4()

        response = await client.delete(
            f"/api/v1/tokens/{fake_id}",
            headers={"Authorization": f"Bearer {expired_jwt}"}
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestGetTokenLogs:
    """Test GET /api/v1/tokens/{token_id}/logs endpoint."""

    async def test_get_token_logs_200_success(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting token audit logs returns 200."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "logs" in data
        assert "total_logs" in data
        assert isinstance(data["logs"], list)

    async def test_get_token_logs_200_with_pagination(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting token logs with limit and offset."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?limit=10&offset=0",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["logs"]) <= 10

    async def test_get_token_logs_404_not_found(
        self, client: AsyncClient, user_a_jwt: str
    ):
        """Test getting logs for nonexistent token returns 404."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/tokens/{fake_id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 404

    async def test_get_token_logs_403_forbidden(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test getting logs for another user's token returns 403."""
        _, token_b = await create_pat_token(user_b.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token_b.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 403

    async def test_get_token_logs_401_no_authorization_header(
        self, client: AsyncClient
    ):
        """Test getting logs without Authorization header returns 401."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/tokens/{fake_id}/logs")
        assert response.status_code == 401

    async def test_get_token_logs_401_invalid_jwt(self, client: AsyncClient):
        """Test getting logs with invalid JWT returns 401."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/tokens/{fake_id}/logs",
            headers={"Authorization": "Bearer invalid_jwt"}
        )
        assert response.status_code == 401

    async def test_get_token_logs_401_expired_jwt(self, client: AsyncClient, user_a: User):
        """Test getting logs with expired JWT returns 401."""
        from app.domain.auth_service import create_access_token

        expired_jwt = create_access_token(
            user_id=user_a.id,
            expires_delta=timedelta(seconds=-1)
        )
        fake_id = uuid4()

        response = await client.get(
            f"/api/v1/tokens/{fake_id}/logs",
            headers={"Authorization": f"Bearer {expired_jwt}"}
        )
        assert response.status_code == 401

    async def test_get_token_logs_422_invalid_limit(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting logs with invalid limit returns 422."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        # Limit too small
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?limit=0",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 422

        # Limit too large
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?limit=2000",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 422

    async def test_get_token_logs_422_invalid_offset(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test getting logs with negative offset returns 422."""
        _, token = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?offset=-1",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 422
