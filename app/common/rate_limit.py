"""Rate limiting utilities."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"]
)


def get_limiter():
    """Get the limiter instance."""
    return limiter
