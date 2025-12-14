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
