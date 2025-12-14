"""Rate limiting utilities."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

# Rate limit string based on settings
RATE_LIMIT = f"{settings.rate_limit_per_minute}/minute"

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT]
)


def get_limiter():
    """Get the limiter instance."""
    return limiter
