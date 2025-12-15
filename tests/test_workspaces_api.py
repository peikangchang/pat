"""Test workspaces API endpoints.

Covers:
- GET /api/v1/workspacess
- POST /api/v1/workspacess
- DELETE /api/v1/workspacess/{id}
- PUT /api/v1/workspacess/{id}/settings

All these endpoints require PAT authentication (stub implementation).
No 404 tests - these are stub APIs that always return success or permission errors.

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
class TestListWorkspaces:
    """Test GET /api/v1/workspacess endpoint."""

    async def test_list_workspaces_200_with_read_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test listing workspaces with workspacess:read permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_list_workspaces_401_no_authorization_header(self, client: AsyncClient):
        """Test listing workspaces without Authorization header returns 401."""
        response = await client.get("/api/v1/workspacess")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_list_workspaces_401_invalid_token(self, client: AsyncClient):
        """Test listing workspaces with invalid PAT token returns 401."""
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": "Bearer pat_invalid_token_123"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_list_workspaces_401_expired_token(
        self, client: AsyncClient, session, user_a: User, create_pat_token
    ):
        """Test listing workspaces with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        # Create an expired token
        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspacess:read"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "expired" in data["message"].lower()

    async def test_list_workspaces_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test listing workspaces with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["workspacess:read"],
            is_revoked=True
        )

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "revoked" in data["message"].lower()

    async def test_list_workspaces_403_insufficient_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test listing workspaces without workspacess:read permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:read"
        assert data["data"]["your_scopes"] == ["fcs:read"]


@pytest.mark.integration
class TestCreateWorkspace:
    """Test POST /api/v1/workspacess endpoint."""

    async def test_create_workspace_200_with_write_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test creating workspace with workspacess:write permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:write"])

        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_create_workspace_401_no_authorization_header(self, client: AsyncClient):
        """Test creating workspace without Authorization header returns 401."""
        response = await client.post("/api/v1/workspacess")
        assert response.status_code == 401

    async def test_create_workspace_401_invalid_token(self, client: AsyncClient):
        """Test creating workspace with invalid PAT token returns 401."""
        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": "Bearer pat_invalid"}
        )
        assert response.status_code == 401

    async def test_create_workspace_401_expired_token(
        self, client: AsyncClient, session, user_a: User, create_pat_token
    ):
        """Test creating workspace with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspacess:write"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401

    async def test_create_workspace_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test creating workspace with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["workspacess:write"],
            is_revoked=True
        )

        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

    async def test_create_workspace_403_read_only_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test creating workspace with only workspacess:read permission returns 403."""
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


@pytest.mark.integration
class TestDeleteWorkspace:
    """Test DELETE /api/v1/workspacess/{id} endpoint."""

    async def test_delete_workspace_200_with_delete_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test deleting workspace with workspacess:delete permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:delete"])

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_delete_workspace_401_no_authorization_header(self, client: AsyncClient):
        """Test deleting workspace without Authorization header returns 401."""
        response = await client.delete("/api/v1/workspacess/test-id")
        assert response.status_code == 401

    async def test_delete_workspace_401_invalid_token(self, client: AsyncClient):
        """Test deleting workspace with invalid PAT token returns 401."""
        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": "Bearer pat_invalid"}
        )
        assert response.status_code == 401

    async def test_delete_workspace_401_expired_token(
        self, client: AsyncClient, session, user_a: User
    ):
        """Test deleting workspace with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspacess:delete"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401

    async def test_delete_workspace_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test deleting workspace with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["workspacess:delete"],
            is_revoked=True
        )

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

    async def test_delete_workspace_403_write_permission_only(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test deleting workspace with only workspacess:write permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:write"])

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403

    async def test_delete_workspace_403_read_permission_only(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test deleting workspace with only workspacess:read permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403


@pytest.mark.integration
class TestUpdateWorkspaceSettings:
    """Test PUT /api/v1/workspacess/{id}/settings endpoint."""

    async def test_update_settings_200_with_admin_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating workspace settings with workspacess:admin permission returns 200."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:admin"])

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_update_settings_401_no_authorization_header(self, client: AsyncClient):
        """Test updating settings without Authorization header returns 401."""
        response = await client.put("/api/v1/workspacess/test-id/settings")
        assert response.status_code == 401

    async def test_update_settings_401_invalid_token(self, client: AsyncClient):
        """Test updating settings with invalid PAT token returns 401."""
        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": "Bearer pat_invalid"}
        )
        assert response.status_code == 401

    async def test_update_settings_401_expired_token(
        self, client: AsyncClient, session, user_a: User
    ):
        """Test updating settings with expired PAT token returns 401."""
        from app.domain.token_service import create_token_info
        from app.models.token import Token

        token_info = create_token_info()
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)

        token = Token(
            user_id=user_a.id,
            name="Expired Token",
            token_hash=token_info.token_hash,
            token_prefix=token_info.token_prefix,
            scopes=["workspacess:admin"],
            expires_at=expired_at,
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )
        assert response.status_code == 401

    async def test_update_settings_401_revoked_token(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating settings with revoked PAT token returns 401."""
        full_token, _ = await create_pat_token(
            user_a.id,
            scopes=["workspacess:admin"],
            is_revoked=True
        )

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

    async def test_update_settings_403_without_admin_permission(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating settings without workspacess:admin permission returns 403."""
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

    async def test_update_settings_403_write_permission_only(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test updating settings with only workspacess:write permission returns 403."""
        full_token, _ = await create_pat_token(user_a.id, scopes=["workspacess:write"])

        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
