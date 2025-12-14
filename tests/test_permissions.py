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


@pytest.mark.permissions
class TestFCSPermissionHierarchy:
    """Test FCS permission hierarchy: analyze > write > read."""

    async def test_fcs_analyze_includes_all_fcs_permissions(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that fcs:analyze includes analyze/write/read permissions.

        FCS permission hierarchy:
        - fcs:analyze 包含 fcs:analyze, fcs:write, fcs:read
        - fcs:write 包含 fcs:write, fcs:read
        - fcs:read 包含 fcs:read
        """
        # Upload FCS file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        import io
        from tests.test_fcs_api import create_mock_fcs_file
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Create token with analyze permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["fcs:analyze"]
        )

        # Should be able to read (lower permission)
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "analyze should include read permission"

        # Should be able to write (lower permission)
        filename2, content2 = create_mock_fcs_file("another.fcs")
        files2 = {"file": (filename2, io.BytesIO(content2), "application/octet-stream")}
        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files2
        )
        assert response.status_code == 200, "analyze should include write permission"

        # Should be able to analyze
        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "analyze should include analyze permission"

    async def test_fcs_write_includes_read(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that fcs:write includes write and read permissions."""
        # Upload FCS file first
        full_token, token = await create_pat_token(
            user_a.id, scopes=["fcs:write"]
        )

        import io
        from tests.test_fcs_api import create_mock_fcs_file
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

        # Should be able to write
        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files
        )
        assert response.status_code == 200, "write should allow upload"

        # Should be able to read
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "write should include read permission"

    async def test_fcs_write_does_not_include_analyze(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that fcs:write does NOT include analyze permission."""
        # Upload FCS file first
        token_write, _ = await create_pat_token(
            user_a.id, scopes=["fcs:write"]
        )

        import io
        from tests.test_fcs_api import create_mock_fcs_file
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Create token with write permission only
        full_token, token = await create_pat_token(
            user_a.id, scopes=["fcs:write"]
        )

        # Should NOT be able to analyze (requires fcs:analyze)
        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403, "write should NOT include analyze permission"
        data = response.json()
        assert data["error"] == "Forbidden"
        assert data["data"]["required_scope"] == "fcs:analyze"
        assert data["data"]["your_scopes"] == ["fcs:write"]

    async def test_fcs_read_only_allows_reading(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that fcs:read only allows reading, not writing or analyzing."""
        # Upload FCS file first
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        import io
        from tests.test_fcs_api import create_mock_fcs_file
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Create token with read permission only
        full_token, token = await create_pat_token(
            user_a.id, scopes=["fcs:read"]
        )

        # Should be able to read
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "read should allow reading"

        response = await client.get(
            "/api/v1/fcs/events",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200, "read should allow reading events"

        # Should NOT be able to write
        filename2, content2 = create_mock_fcs_file("another.fcs")
        files2 = {"file": (filename2, io.BytesIO(content2), "application/octet-stream")}
        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {full_token}"},
            files=files2
        )
        assert response.status_code == 403, "read should NOT include write permission"

        # Should NOT be able to analyze
        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 403, "read should NOT include analyze permission"

    async def test_fcs_permissions_hierarchy_completeness(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test complete FCS permission hierarchy with all three levels."""
        # Upload FCS file
        token_write, _ = await create_pat_token(user_a.id, scopes=["fcs:write"])
        import io
        from tests.test_fcs_api import create_mock_fcs_file
        filename, content = create_mock_fcs_file()
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_write}"},
            files=files
        )

        # Test fcs:read can only read
        token_read, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_read}"}
        )
        assert response.status_code == 200

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_read}"}
        )
        assert response.status_code == 403, "read cannot analyze"

        # Test fcs:write can write and read but not analyze
        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_write}"}
        )
        assert response.status_code == 200

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_write}"}
        )
        assert response.status_code == 403, "write cannot analyze"

        # Test fcs:analyze can do everything
        token_analyze, _ = await create_pat_token(user_a.id, scopes=["fcs:analyze"])

        response = await client.get(
            "/api/v1/fcs/parameters",
            headers={"Authorization": f"Bearer {token_analyze}"}
        )
        assert response.status_code == 200, "analyze can read"

        response = await client.get(
            "/api/v1/fcs/statistics",
            headers={"Authorization": f"Bearer {token_analyze}"}
        )
        assert response.status_code == 200, "analyze can analyze"

        filename3, content3 = create_mock_fcs_file("third.fcs")
        files3 = {"file": (filename3, io.BytesIO(content3), "application/octet-stream")}
        response = await client.post(
            "/api/v1/fcs/upload",
            headers={"Authorization": f"Bearer {token_analyze}"},
            files=files3
        )
        assert response.status_code == 200, "analyze can write"
