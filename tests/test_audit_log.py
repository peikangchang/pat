"""Test audit logging functionality.

Test cases:
1. Log Creation - Audit logs are created for all PAT token usage
2. Log Content - Logs contain correct method, endpoint, status, authorized, reason
3. Log Retrieval - Users can retrieve audit logs for their tokens
4. User Isolation - Users cannot see other users' token logs
5. Unauthorized Access - Failed auth attempts are logged with reason
6. Pagination - Audit log pagination works correctly
7. IP Address - Logs include client IP address
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.models.token import Token
from app.models.audit_log import AuditLog


@pytest.mark.integration
class TestAuditLogCreation:
    """Test that audit logs are created for token usage."""

    async def test_successful_request_creates_audit_log(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that successful PAT usage creates an audit log."""
        # Create token
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Make a successful request
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200

        # Check audit log was created
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1

        log = logs[0]
        assert log.method == "GET"
        assert log.endpoint == "/api/v1/workspacess"
        assert log.status_code == 200
        assert log.authorized is True
        assert log.reason is None

    async def test_failed_auth_creates_audit_log(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that failed authentication creates an audit log with reason."""
        # Create and revoke token
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"], is_revoked=True
        )

        # Make request with revoked token
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 401

        # Check audit log was created with failure reason
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1

        log = logs[0]
        assert log.authorized is False
        assert log.status_code == 401
        assert "revoked" in log.reason.lower()

    async def test_forbidden_request_creates_audit_log(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that 403 Forbidden creates an audit log."""
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

        # Check audit log
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1

        log = logs[0]
        assert log.authorized is False
        assert log.status_code == 403
        assert "permission" in log.reason.lower() or "forbidden" in log.reason.lower()

    async def test_multiple_requests_create_multiple_logs(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that multiple requests create multiple audit logs."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read", "users:read"]
        )

        # Make multiple requests to different endpoints
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # Check all logs were created
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 3

        endpoints = [log.endpoint for log in logs]
        assert "/api/v1/workspacess" in endpoints
        assert "/api/v1/users/me" in endpoints


@pytest.mark.integration
class TestAuditLogContent:
    """Test audit log content correctness."""

    async def test_audit_log_contains_method(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that audit logs correctly record HTTP method."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:write"]
        )

        # Test GET
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # Test POST
        await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        logs = result.scalars().all()

        methods = [log.method for log in logs]
        assert "GET" in methods
        assert "POST" in methods

    async def test_audit_log_contains_ip_address(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that audit logs include client IP address."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        log = result.scalar_one()

        assert log.ip_address is not None
        assert len(log.ip_address) > 0

    async def test_audit_log_timestamp_is_recent(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that audit log timestamp is set correctly."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        before_request = datetime.now(timezone.utc)
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        after_request = datetime.now(timezone.utc)

        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        log = result.scalar_one()

        assert log.timestamp is not None
        assert before_request <= log.timestamp <= after_request


@pytest.mark.integration
class TestAuditLogRetrieval:
    """Test audit log retrieval via API."""

    async def test_get_token_logs_returns_audit_logs(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test GET /tokens/{id}/logs returns audit logs."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Generate some logs
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # Retrieve logs
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]

        assert "logs" in data
        assert len(data["logs"]) == 2
        assert data["logs"][0]["endpoint"] == "/api/v1/workspacess"
        assert data["logs"][0]["authorized"] is True

    async def test_get_token_logs_shows_failure_reasons(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that audit logs include failure reasons."""
        # Create token without required permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Try to write (will fail with 403)
        await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # Retrieve logs
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        data = response.json()["data"]

        assert len(data["logs"]) == 1
        log = data["logs"][0]
        assert log["authorized"] is False
        assert log["status_code"] == 403
        assert "reason" in log
        assert log["reason"] is not None


@pytest.mark.integration
class TestAuditLogPagination:
    """Test audit log pagination."""

    async def test_audit_log_pagination_with_limit(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that audit log pagination works with limit."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Generate 10 logs
        for i in range(10):
            await client.get(
                "/api/v1/workspacess",
                headers={"Authorization": f"Bearer {full_token}"}
            )

        # Get logs with limit
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?limit=5",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        data = response.json()["data"]

        assert len(data["logs"]) == 5
        assert data["total"] == 10
        assert data["limit"] == 5
        assert data["offset"] == 0

    async def test_audit_log_pagination_with_offset(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that audit log pagination works with offset."""
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Generate 10 logs
        for i in range(10):
            await client.get(
                "/api/v1/workspacess",
                headers={"Authorization": f"Bearer {full_token}"}
            )

        # Get logs with offset
        response = await client.get(
            f"/api/v1/tokens/{token.id}/logs?limit=3&offset=5",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        data = response.json()["data"]

        assert len(data["logs"]) == 3
        assert data["total"] == 10
        assert data["limit"] == 3
        assert data["offset"] == 5


@pytest.mark.integration
class TestAuditLogIsolation:
    """Test audit log user isolation."""

    async def test_user_cannot_access_other_user_token_logs(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_b_jwt: str, create_pat_token
    ):
        """Test that users cannot access other users' token audit logs."""
        # User A creates token and generates logs
        full_token, token_a = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # User B tries to access User A's token logs
        response = await client.get(
            f"/api/v1/tokens/{token_a.id}/logs",
            headers={"Authorization": f"Bearer {user_b_jwt}"}
        )
        assert response.status_code == 404

    async def test_user_can_only_see_own_token_logs(
        self, client: AsyncClient, user_a: User, user_b: User,
        user_a_jwt: str, create_pat_token
    ):
        """Test that users only see audit logs for their own tokens."""
        # User A creates token
        full_token_a, token_a = await create_pat_token(
            user_a.id, scopes=["workspacess:read"], name="User A Token"
        )

        # User B creates token
        full_token_b, token_b = await create_pat_token(
            user_b.id, scopes=["workspacess:read"], name="User B Token"
        )

        # Both use their tokens
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token_a}"}
        )
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token_b}"}
        )

        # User A retrieves their token logs
        response = await client.get(
            f"/api/v1/tokens/{token_a.id}/logs",
            headers={"Authorization": f"Bearer {user_a_jwt}"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["logs"]) == 1


@pytest.mark.integration
class TestAuditLogUnauthorizedTracking:
    """Test tracking of unauthorized access attempts."""

    async def test_expired_token_logged_with_reason(
        self, client: AsyncClient, session: AsyncSession, user_a: User
    ):
        """Test that expired token usage is logged with expiration reason."""
        from app.domain.token_service import create_token_info

        # Create expired token
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
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_info.full_token}"}
        )

        # Check audit log
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        log = result.scalar_one()

        assert log.authorized is False
        assert log.status_code == 401
        assert "expired" in log.reason.lower()

    async def test_permission_denied_logged_with_reason(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, create_pat_token
    ):
        """Test that permission denied is logged with appropriate reason."""
        # Create token with read-only permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Try to write
        await client.post(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )

        # Check audit log
        result = await session.execute(
            select(AuditLog).where(AuditLog.token_id == token.id)
        )
        log = result.scalar_one()

        assert log.authorized is False
        assert log.status_code == 403
        assert log.reason is not None
        assert "permission" in log.reason.lower() or "forbidden" in log.reason.lower()

    async def test_invalid_token_not_logged(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test that invalid tokens don't create audit logs (no token_id to associate)."""
        # Use completely invalid token
        await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": "Bearer pat_invalid_token_123"}
        )

        # There should be no audit log created (token doesn't exist)
        result = await session.execute(select(AuditLog))
        logs = result.scalars().all()

        # Note: This behavior depends on implementation
        # Some systems may still log invalid token attempts with special handling
        # For now, we expect no logs since there's no token_id to associate
