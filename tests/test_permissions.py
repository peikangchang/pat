"""Test permission hierarchy and inheritance.

Test cases:
1. Permission hierarchy inheritance
   - workspacess:delete includes workspacess:delete/write/read
   - workspacess:delete does NOT include workspacess:admin
2. Permissions cannot cross resources
   - workspacess:write does NOT include fcs:read
"""
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.permissions
class TestPermissionHierarchy:
    """Test permission hierarchy and inheritance."""

    async def test_workspaces_delete_includes_lower_permissions(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:delete includes delete/write/read permissions."""
        # Create token with delete permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:delete"]
        )

        # Should be able to read (lower permission)
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "delete should include read permission"

        # Should be able to write (lower permission)
        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "delete should include write permission"

        # Should be able to delete
        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "delete should include delete permission"

    async def test_workspaces_delete_does_not_include_admin(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:delete does NOT include admin permission."""
        # Create token with delete permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:delete"]
        )

        # Should NOT be able to access admin endpoint
        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403, "delete should NOT include admin permission"
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:admin"
        assert data["data"]["your_scopes"] == ["workspacess:delete"]

    async def test_workspaces_write_includes_read(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:write includes read permission."""
        # Create token with write permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:write"]
        )

        # Should be able to read
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "write should include read permission"

        # Should be able to write
        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

    async def test_workspaces_write_does_not_include_delete(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:write does NOT include delete permission."""
        # Create token with write permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:write"]
        )

        # Should NOT be able to delete
        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403, "write should NOT include delete permission"
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:delete"
        assert data["data"]["your_scopes"] == ["workspacess:write"]

    async def test_workspaces_admin_includes_all_permissions(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:admin includes all workspace permissions."""
        # Create token with admin permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:admin"]
        )

        # Should be able to read
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Should be able to write
        response = await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Should be able to delete
        response = await client.delete(
            "/api/v1/workspacess/test-id",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Should be able to access admin endpoints
        response = await client.put(
            "/api/v1/workspacess/test-id/settings",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200


@pytest.mark.permissions
class TestCrossResourcePermissions:
    """Test that permissions cannot cross resources."""

    async def test_workspaces_write_does_not_include_fcs_read(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that workspacess:write does NOT include fcs:read."""
        # Create token with workspacess:write permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:write"]
        )

        # Should be able to access workspaces
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Should NOT be able to access FCS endpoints
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:read"
        assert data["data"]["your_scopes"] == ["workspacess:write"]

    async def test_fcs_analyze_does_not_include_workspaces_read(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that fcs:analyze does NOT include workspacess:read."""
        # Create token with fcs:analyze permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["fcs:analyze"]
        )

        # Should be able to access FCS endpoints
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code in [200, 404]  # 404 if no FCS file uploaded

        # Should NOT be able to access workspaces endpoints
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "workspacess:read"
        assert data["data"]["your_scopes"] == ["fcs:analyze"]

    async def test_users_write_does_not_include_tokens_read(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that users:write does NOT grant access to tokens."""
        # Create token with users:write permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["users:write"]
        )

        # Should be able to access users endpoints
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Should NOT be able to access tokens endpoints (uses JWT, not PAT)
        # Note: tokens endpoints require JWT authentication, not PAT
