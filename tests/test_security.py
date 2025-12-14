"""Test security features: password hashing, token storage, authentication, lifecycle.

Test cases:
1. Password Security - Argon2 hashing, no plaintext storage
2. Token Storage - Tokens stored as hash+prefix, not plaintext
3. Token Format - PAT tokens have correct prefix format (pat_ + 8 chars)
4. Token Authentication - Valid/invalid/malformed token handling
5. Token Expiration - Expired tokens cannot be used
6. Token Revocation - Revoked tokens cannot be used
7. Valid Tokens - Work correctly with proper permissions
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.models.user import User
from app.models.token import Token
from app.domain.token_service import create_token_info


@pytest.mark.security
class TestPasswordSecurity:
    """Test password hashing with Argon2."""

    async def test_password_not_stored_in_plaintext(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test that passwords are hashed with Argon2, not stored as plaintext."""
        # Register a new user
        password = "SecurePassword123!"
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "secureuser",
                "email": "secure@example.com",
                "password": password
            }
        )
        assert response.status_code == 200
        user_id = response.json()["data"]["id"]

        # Check database - password should be hashed
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user_in_db = result.scalar_one()

        # Hashed password should not be the plaintext
        assert user_in_db.password_hash != password
        assert user_in_db.password_hash.startswith("$argon2")

    async def test_argon2_password_verification_works(
        self, client: AsyncClient, user_a: User
    ):
        """Test that Argon2 hashed passwords can be verified correctly."""
        # Login with correct password should work
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "password123"
            }
        )
        assert response.status_code == 200
        assert "access_token" in response.json()["data"]

        # Login with wrong password should fail
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "user_a",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    async def test_argon2_hash_format(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test that password hashes use correct Argon2 format."""
        # Register user
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "hashtest",
                "email": "hash@example.com",
                "password": "TestPassword123!"
            }
        )
        user_id = response.json()["data"]["id"]

        # Check hash format
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one()

        # Argon2 hash should start with $argon2
        hash_str = user.password_hash
        assert hash_str.startswith("$argon2")
        # Typical Argon2 hash is long (80+ characters)
        assert len(hash_str) > 80


@pytest.mark.security
class TestTokenStorage:
    """Test that PAT tokens are stored securely."""

    async def test_token_not_stored_in_plaintext(
        self, client: AsyncClient, session: AsyncSession,
        user_a: User, user_a_jwt: str
    ):
        """Test that PAT full token is not stored in database, only hash and prefix."""
        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Security Test Token",
                "scopes": ["workspacess:read"],
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
        """Test that same token produces same hash (SHA-256 deterministic)."""
        from app.domain.token_service import hash_token

        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Hash Test Token",
                "scopes": ["workspacess:read"],
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
class TestTokenFormat:
    """Test PAT token prefix format."""

    async def test_token_prefix_format(
        self, client: AsyncClient, user_a: User, user_a_jwt: str
    ):
        """Test that token prefix is 'pat_' followed by 8 characters."""
        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Format Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        token_prefix = data["token_prefix"]

        # Should start with "pat_"
        assert token_prefix.startswith("pat_")

        # Should be "pat_" + 8 characters = 12 total
        assert len(token_prefix) == 12

        # Characters after "pat_" should be alphanumeric
        prefix_chars = token_prefix[4:]  # Get the 8 chars after "pat_"
        assert len(prefix_chars) == 8
        assert prefix_chars.isalnum()

    async def test_full_token_contains_prefix(
        self, client: AsyncClient, user_a: User, user_a_jwt: str
    ):
        """Test that full token starts with the prefix."""
        # Create token
        response = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Prefix Test Token",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        data = response.json()["data"]
        full_token = data["token"]
        token_prefix = data["token_prefix"]

        # Full token should start with prefix
        assert full_token.startswith(token_prefix)
        # Full token should be longer than prefix
        assert len(full_token) > len(token_prefix)

    async def test_token_prefix_is_unique(
        self, client: AsyncClient, user_a: User, user_a_jwt: str
    ):
        """Test that different tokens have different prefixes."""
        # Create first token
        response1 = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Token 1",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        prefix1 = response1.json()["data"]["token_prefix"]

        # Create second token
        response2 = await client.post(
            "/api/v1/tokens",
            headers={"Authorization": f"Bearer {user_a_jwt}"},
            json={
                "name": "Token 2",
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        prefix2 = response2.json()["data"]["token_prefix"]

        # Prefixes should be different (extremely high probability)
        assert prefix1 != prefix2


@pytest.mark.security
class TestTokenAuthentication:
    """Test token authentication scenarios."""

    async def test_valid_token_with_permission_returns_200(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that valid token with correct permission works."""
        # Create token with workspacess:read permission
        full_token, token = await create_pat_token(
            user_a.id, scopes=["workspacess:read"]
        )

        # Should successfully access resource
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {full_token}"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_invalid_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that invalid token returns 401 with Unauthorized error."""
        # Use completely invalid token
        invalid_token = "pat_invalid_token_1234567890"

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {invalid_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"
        assert response.json()["message"] == "Invalid token"

    async def test_malformed_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that malformed token (not starting with pat_) returns 401."""
        # Use malformed token
        malformed_token = "not_a_valid_token"

        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"
        assert response.json()["message"] == "Invalid token"

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
                "scopes": ["workspacess:read"],
                "expires_in_days": 30
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        token_prefix = data["token_prefix"]

        # Try to use prefix token for authentication
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": f"Bearer {token_prefix}"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"
        assert response.json()["message"] == "Invalid token"

    async def test_missing_authorization_header_returns_401(
        self, client: AsyncClient
    ):
        """Test that missing authorization header returns 401."""
        response = await client.get("/api/v1/workspacess")
        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    async def test_invalid_authorization_header_format_returns_401(
        self, client: AsyncClient
    ):
        """Test that invalid authorization header format returns 401."""
        # Missing "Bearer" prefix
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": "pat_token123"}
        )
        assert response.status_code == 401

        # Wrong prefix
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": "Basic pat_token123"}
        )
        assert response.status_code == 401

    async def test_empty_token_returns_401(
        self, client: AsyncClient
    ):
        """Test that empty token returns 401."""
        response = await client.get(
            "/api/v1/workspacess",
            headers={"Authorization": "Bearer "}
        )
        assert response.status_code == 401


@pytest.mark.security
class TestTokenExpiration:
    """Test token expiration handling."""

    async def test_expired_token_returns_401(
        self, client: AsyncClient, session: AsyncSession, user_a: User
    ):
        """Test that expired token returns 401 with 'Token expired' message."""
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
        assert response.json()["error"] == "Unauthorized"
        assert response.json()["message"] == "Token expired"

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


@pytest.mark.security
class TestTokenRevocation:
    """Test token revocation handling."""

    async def test_revoked_token_returns_401(
        self, client: AsyncClient, user_a: User, user_a_jwt: str, create_pat_token
    ):
        """Test that revoked token returns 401 with 'Token revoked' message."""
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
        assert response.json()["error"] == "Unauthorized"
        assert response.json()["message"] == "Token revoked"

    async def test_revoke_operation_is_idempotent(
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


@pytest.mark.security
class TestValidToken:
    """Test that valid tokens work correctly with permissions."""

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
