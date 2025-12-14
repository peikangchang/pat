"""Test rate limiting configuration.

Test cases:
- RATE_LIMIT constant is correctly set from settings
- Rate limit actually enforces the configured value
- Changing rate_limit_per_minute affects actual rate limiting behavior
"""
import pytest
import os
import importlib
from httpx import AsyncClient


@pytest.mark.unit
class TestRateLimitConfiguration:
    """Test that rate limiting configuration works correctly."""

    def test_rate_limit_constant_matches_settings(self):
        """Test that RATE_LIMIT constant is set from settings.rate_limit_per_minute."""
        from app.common.config import settings
        from app.common.rate_limit import RATE_LIMIT

        # RATE_LIMIT should be in format "{number}/minute"
        expected = f"{settings.rate_limit_per_minute}/minute"
        assert RATE_LIMIT == expected

    def test_rate_limit_uses_configured_value(self):
        """Test that rate limit uses the configured value from settings."""
        from app.common.config import settings
        from app.common.rate_limit import RATE_LIMIT

        # Should match settings
        assert RATE_LIMIT == f"{settings.rate_limit_per_minute}/minute"

    def test_rate_limit_format_is_valid(self):
        """Test that RATE_LIMIT has valid format for slowapi."""
        from app.common.rate_limit import RATE_LIMIT

        # Should be in format "number/minute"
        parts = RATE_LIMIT.split('/')
        assert len(parts) == 2
        assert parts[1] == "minute"
        assert parts[0].isdigit()
        assert int(parts[0]) > 0


@pytest.mark.integration
class TestRateLimitEnforcement:
    """Test that rate limiting actually enforces the configured limits."""

    async def test_rate_limit_shared_across_endpoints(self, client: AsyncClient):
        """Test that rate limit is shared across all endpoints.

        This test verifies that application_limits creates a shared counter,
        meaning requests to different endpoints count towards the same limit.

        For example, with a 60/minute limit:
        - 30 requests to /login + 31 requests to /register should trigger rate limit
        - Not 60 requests to each endpoint independently
        """
        import asyncio
        from app.common.rate_limit import limiter
        from app.common.config import settings

        # Enable rate limiting for this test
        original_enabled = limiter.enabled
        limiter.enabled = True

        # Reset rate limiter storage to ensure clean slate
        # This clears any rate limit state from previous tests
        # Access the underlying limits library storage
        if hasattr(limiter, '_limiter') and hasattr(limiter._limiter, 'storage'):
            # Clear the storage backend
            storage = limiter._limiter.storage
            if hasattr(storage, 'reset'):
                storage.reset()
            elif hasattr(storage, 'storage'):
                # For MemoryStorage, clear the internal dict
                storage.storage.clear()

        try:
            limit = settings.rate_limit_per_minute

            # Make requests to different endpoints
            # Split the limit across two different endpoints
            requests_per_endpoint = limit // 2

            # First half: requests to /login
            for i in range(requests_per_endpoint):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "testpass"}
                )
                # These should not trigger rate limit yet
                assert response.status_code != 429, f"Rate limit triggered too early at request {i+1}/{requests_per_endpoint}"

            # Second half: requests to /register
            # The last few of these should trigger rate limit
            rate_limited = False
            for i in range(requests_per_endpoint + 10):  # Try more to ensure we hit the limit
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": f"newuser{i}",
                        "email": f"user{i}@example.com",
                        "password": "password123"
                    }
                )

                if response.status_code == 429:
                    # Rate limit triggered - verify response format
                    data = response.json()
                    assert data["success"] is False
                    assert data["error"] == "Too Many Requests"
                    assert "retry_after" in data["data"]
                    assert data["data"]["retry_after"] > 0
                    rate_limited = True
                    break

            # Verify that rate limit was triggered
            # This proves that both endpoints share the same counter
            assert rate_limited, (
                f"Rate limit should have been triggered by requests to different endpoints. "
                f"Made {requests_per_endpoint} requests to /login and {requests_per_endpoint + 10} to /register "
                f"with a total limit of {limit}. This indicates endpoints may have separate counters."
            )

        finally:
            # Restore original state
            limiter.enabled = original_enabled

    async def test_rate_limit_enforces_configured_value(self, client: AsyncClient):
        """Test that rate limiter actually enforces the configured limit.

        This test verifies that when RATE_LIMIT_PER_MINUTE is set to a specific
        value, the rate limiter actually blocks requests beyond that limit.
        """
        from app.common.rate_limit import limiter
        from app.common.config import settings

        # Enable rate limiting for this test
        original_enabled = limiter.enabled
        limiter.enabled = True

        try:
            # Current configured limit
            limit = settings.rate_limit_per_minute

            # Make (limit + 1) requests to trigger rate limit
            rate_limited = False
            for i in range(limit + 10):  # Try more than the limit
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "testpass"}
                )

                if response.status_code == 429:
                    # Rate limit triggered
                    data = response.json()
                    assert data["success"] is False
                    assert data["error"] == "Too Many Requests"
                    assert "retry_after" in data["data"]
                    rate_limited = True
                    break

            # Verify rate limit was actually triggered
            assert rate_limited, f"Rate limit should have triggered after {limit} requests"

        finally:
            # Restore original state
            limiter.enabled = original_enabled

    def test_rate_limit_configuration_from_environment(self, monkeypatch):
        """Test that RATE_LIMIT_PER_MINUTE environment variable is read correctly.

        This test demonstrates that setting RATE_LIMIT_PER_MINUTE in the
        environment (e.g., in .env file or docker-compose.yml) will configure
        the rate limit correctly when the application starts.
        """
        import importlib

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
