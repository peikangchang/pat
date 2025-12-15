"""Test rate limiting functionality.

Test cases:
1. Configuration - RATE_LIMIT constant is correctly set from settings
2. Shared counter - All endpoints share the same rate limit counter
3. Enforcement - Rate limit actually blocks requests beyond the limit
4. Response format - 429 responses include correct retry_after time
5. All requests count - Both successful and failed requests count towards limit
6. Multiple endpoints - Different endpoint combinations trigger shared limit

NOTE: These tests should be run separately from other tests to avoid rate limit
pollution. Use: pytest tests/test_rate_limiting.py
"""
import pytest
import importlib
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.unit
class TestRateLimitConfiguration:
    """Test rate limiting configuration from environment and settings."""

    def test_rate_limit_constant_matches_settings(self):
        """Test that RATE_LIMIT constant is set from settings.rate_limit_per_minute."""
        from app.common.config import settings
        from app.common.rate_limit import RATE_LIMIT

        # RATE_LIMIT should be in format "{number}/minute"
        expected = f"{settings.rate_limit_per_minute}/minute"
        assert RATE_LIMIT == expected

    def test_rate_limit_format_is_valid(self):
        """Test that RATE_LIMIT has valid format for slowapi."""
        from app.common.rate_limit import RATE_LIMIT

        # Should be in format "number/minute"
        parts = RATE_LIMIT.split('/')
        assert len(parts) == 2
        assert parts[1] == "minute"
        assert parts[0].isdigit()
        assert int(parts[0]) > 0

    def test_rate_limit_configuration_from_environment(self, monkeypatch):
        """Test that RATE_LIMIT_PER_MINUTE environment variable is read correctly."""
        # Set environment variable before loading modules
        monkeypatch.setenv('RATE_LIMIT_PER_MINUTE', '100')

        # Reload config and rate_limit modules to pick up the env var
        import app.common.config
        import app.common.rate_limit
        importlib.reload(app.common.config)
        importlib.reload(app.common.rate_limit)

        # Import after reload
        from app.common.config import settings
        from app.common.rate_limit import RATE_LIMIT

        # Verify the new configuration was applied
        assert settings.rate_limit_per_minute == 100
        assert RATE_LIMIT == "100/minute"

        # Clean up: reload with original environment
        monkeypatch.delenv('RATE_LIMIT_PER_MINUTE', raising=False)
        importlib.reload(app.common.config)
        importlib.reload(app.common.rate_limit)

        # IMPORTANT: Update app.state.limiter to point to the reloaded limiter
        # After reload, limiter is a new instance, but app.state.limiter still points to old one
        from app.main import app
        from app.common.rate_limit import limiter
        app.state.limiter = limiter


@pytest.mark.integration
class TestRateLimitSharedCounter:
    """Test that rate limit is shared across all endpoints using application_limits."""

    async def test_rate_limit_shared_across_auth_endpoints(self, client: AsyncClient):
        """Test that /login and /register share the same rate limit counter.

        This verifies application_limits creates a shared counter.
        With a 60/minute limit:
        - 30 requests to /login + 31 requests to /register should trigger rate limit
        - Not 60 requests to each endpoint independently
        """
        from app.common.rate_limit import limiter
        from app.common.config import settings

        # Enable rate limiting for this test
        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset rate limiter storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'reset'):
                storage.reset()
            elif hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute
            requests_per_endpoint = limit // 2

            # First half: requests to /login
            for i in range(requests_per_endpoint):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "testpass"}
                )
                assert response.status_code != 429, f"Rate limit triggered too early at request {i+1}"

            # Second half: requests to /register
            rate_limited = False
            for i in range(requests_per_endpoint + 10):
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": f"newuser{i}",
                        "email": f"user{i}@example.com",
                        "password": "password123"
                    }
                )

                if response.status_code == 429:
                    data = response.json()
                    assert data["success"] is False
                    assert data["error"] == "Too Many Requests"
                    assert "retry_after" in data["data"]
                    assert data["data"]["retry_after"] > 0
                    rate_limited = True
                    break

            assert rate_limited, (
                f"Rate limit should have been triggered. "
                f"Made {requests_per_endpoint} to /login + {requests_per_endpoint + 10} to /register "
                f"with limit {limit}. Endpoints may have separate counters."
            )

        finally:
            limiter.enabled = original_enabled

    async def test_rate_limit_shared_across_all_endpoints(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that auth, token, and other endpoints all share the same counter."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute
            token, _ = await create_pat_token(user_a.id, scopes=["workspacess:read"])

            # Make requests to different API groups
            requests_made = 0

            # Auth endpoints
            for i in range(limit // 3):
                await client.post(
                    "/api/v1/auth/login",
                    json={"username": "test", "password": "test"}
                )
                requests_made += 1

            # PAT-protected endpoints
            for i in range(limit // 3):
                await client.get(
                    "/api/v1/workspacess",
                    headers={"Authorization": f"Bearer {token}"}
                )
                requests_made += 1

            # Continue until rate limit
            rate_limited = False
            for i in range(limit):
                response = await client.get("/health")
                if response.status_code == 429:
                    rate_limited = True
                    break
                requests_made += 1

            assert rate_limited, f"Rate limit should trigger across all endpoints"

        finally:
            limiter.enabled = original_enabled


@pytest.mark.integration
class TestRateLimitEnforcement:
    """Test that rate limiting enforces the configured limits."""

    async def test_rate_limit_enforces_configured_value(self, client: AsyncClient):
        """Test that rate limiter blocks requests beyond the configured limit."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Make (limit + 10) requests to ensure we hit the limit
            rate_limited = False
            for i in range(limit + 10):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "testpass"}
                )

                if response.status_code == 429:
                    data = response.json()
                    assert data["success"] is False
                    assert data["error"] == "Too Many Requests"
                    assert "retry_after" in data["data"]
                    rate_limited = True
                    break

            assert rate_limited, f"Rate limit should trigger after {limit} requests"

        finally:
            limiter.enabled = original_enabled

    async def test_rate_limit_blocks_all_endpoints(self, client: AsyncClient):
        """Test that once rate limit is hit, all endpoints return 429."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Exhaust the rate limit
            for i in range(limit + 5):
                await client.get("/health")

            # Now all endpoints should return 429
            response1 = await client.post(
                "/api/v1/auth/login",
                json={"username": "test", "password": "test"}
            )
            assert response1.status_code == 429

            response2 = await client.post(
                "/api/v1/auth/register",
                json={"username": "new", "email": "new@test.com", "password": "pass123"}
            )
            assert response2.status_code == 429

            response3 = await client.get("/health")
            assert response3.status_code == 429

        finally:
            limiter.enabled = original_enabled


@pytest.mark.integration
class TestRateLimitResponseFormat:
    """Test the 429 response format and content."""

    async def test_429_response_format(self, client: AsyncClient):
        """Test that 429 response has correct format with retry_after."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Exhaust rate limit
            for i in range(limit + 5):
                response = await client.get("/health")
                if response.status_code == 429:
                    break

            # Get a 429 response
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "test", "password": "test"}
            )

            assert response.status_code == 429
            data = response.json()

            # Verify response structure
            assert "success" in data
            assert data["success"] is False
            assert "error" in data
            assert data["error"] == "Too Many Requests"
            assert "data" in data
            assert "retry_after" in data["data"]

            # Verify retry_after is a positive integer
            retry_after = data["data"]["retry_after"]
            assert isinstance(retry_after, int)
            assert retry_after > 0
            assert retry_after <= 60  # Should be within a minute

        finally:
            limiter.enabled = original_enabled

    async def test_429_includes_rate_limit_info(self, client: AsyncClient):
        """Test that 429 response includes helpful rate limit information."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Trigger rate limit
            for i in range(limit + 5):
                response = await client.get("/health")
                if response.status_code == 429:
                    break

            data = response.json()

            # Verify response includes rate limit info
            assert response.status_code == 429
            assert data["error"] == "Too Many Requests"
            assert "retry_after" in data["data"]

        finally:
            limiter.enabled = original_enabled


@pytest.mark.integration
class TestRateLimitCounting:
    """Test what requests count towards the rate limit."""

    async def test_successful_requests_count_towards_limit(
        self, client: AsyncClient, user_a: User
    ):
        """Test that successful (200) requests count towards rate limit."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Make requests that will succeed (200)
            success_count = 0
            for i in range(limit + 10):
                response = await client.get("/health")
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    break

            # We should have gotten close to the limit in successful requests
            assert success_count >= limit - 5, "Successful requests should count towards limit"

        finally:
            limiter.enabled = original_enabled

    async def test_failed_requests_count_towards_limit(self, client: AsyncClient):
        """Test that failed requests (401, 422) also count towards rate limit."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Make requests that will fail (401 Unauthorized)
            for i in range(limit + 5):
                response = await client.get("/api/v1/workspacess")
                if response.status_code == 429:
                    # Rate limit was triggered by failed requests
                    assert True
                    return

            # If we get here, rate limit wasn't triggered
            pytest.fail("Failed requests should count towards rate limit")

        finally:
            limiter.enabled = original_enabled

    async def test_mixed_status_codes_all_count(
        self, client: AsyncClient, user_a: User, create_pat_token
    ):
        """Test that requests with different status codes all count towards limit."""
        from app.common.rate_limit import limiter
        from app.common.config import settings

        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            storage = limiter._limiter.storage
            if hasattr(storage, 'storage'):
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute
            token, _ = await create_pat_token(user_a.id, scopes=["fcs:read"])

            requests_made = 0

            # Mix of different response types
            for i in range(limit // 3):
                # 200 - health check
                await client.get("/health")
                requests_made += 1

                # 401 - no auth
                await client.get("/api/v1/workspacess")
                requests_made += 1

                # 403 - wrong permission
                await client.get(
                    "/api/v1/workspacess",
                    headers={"Authorization": f"Bearer {token}"}
                )
                requests_made += 1

            # Continue until rate limit
            rate_limited = False
            for i in range(limit):
                response = await client.get("/health")
                if response.status_code == 429:
                    rate_limited = True
                    break
                requests_made += 1

            assert rate_limited, "All requests regardless of status code should count"

        finally:
            limiter.enabled = original_enabled
