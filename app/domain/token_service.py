"""PAT token generation and validation service."""
import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# Token configuration
TOKEN_PREFIX = "pat_"
TOKEN_RANDOM_LENGTH = 32  # Length of random part (after prefix)
TOKEN_CHARSET = string.ascii_letters + string.digits  # a-zA-Z0-9


@dataclass
class TokenInfo:
    """Information about a generated token (returned only once at creation)."""

    full_token: str  # Only shown once
    token_hash: str  # Stored in database
    token_prefix: str  # Stored in database for display


def generate_pat_token() -> str:
    """Generate a new PAT token.

    Format: pat_<32_random_chars>
    Example: pat_7x9K2mN4pQ8vR1wS3jL6hB5cF0dG9zA1

    Returns:
        The full PAT token string
    """
    random_part = "".join(
        secrets.choice(TOKEN_CHARSET) for _ in range(TOKEN_RANDOM_LENGTH)
    )
    return TOKEN_PREFIX + random_part


def hash_token(token: str) -> str:
    """Hash a token using SHA-256.

    Args:
        token: The full token string to hash

    Returns:
        Hexadecimal string of the hash (64 characters)
    """
    return hashlib.sha256(token.encode()).hexdigest()


def extract_token_prefix(token: str) -> str:
    """Extract the prefix part of a token for display/lookup.

    The prefix includes 'pat_' plus the first 8 characters of the random part.
    Example: 'pat_7x9K2mN4'

    Args:
        token: The full token string

    Returns:
        The prefix portion (12 characters total: 4 for 'pat_' + 8 random)

    Raises:
        ValueError: If token format is invalid
    """
    if not token.startswith(TOKEN_PREFIX):
        raise ValueError("Invalid token format: must start with 'pat_'")

    if len(token) < len(TOKEN_PREFIX) + 8:
        raise ValueError("Invalid token format: too short")

    # Return pat_ + first 8 chars of random part
    return token[: len(TOKEN_PREFIX) + 8]


def validate_token_format(token: str) -> bool:
    """Validate that a token has the correct format.

    Args:
        token: The token string to validate

    Returns:
        True if format is valid, False otherwise
    """
    # Check prefix
    if not token.startswith(TOKEN_PREFIX):
        return False

    # Check total length
    expected_length = len(TOKEN_PREFIX) + TOKEN_RANDOM_LENGTH
    if len(token) != expected_length:
        return False

    # Check that random part only contains valid characters
    random_part = token[len(TOKEN_PREFIX) :]
    return all(c in TOKEN_CHARSET for c in random_part)


def calculate_expiry_date(days: int | None = None) -> datetime:
    """Calculate token expiry date with UTC timezone.

    Args:
        days: Number of days until expiry. Common values:
            - 30: 30 days
            - 90: 90 days
            - 365: 1 year
            - None or custom value: custom expiry

    Returns:
        Datetime object representing the expiry date (with UTC timezone)
    """
    if days is None:
        days = 90  # Default to 90 days

    return datetime.now(timezone.utc) + timedelta(days=days)


def is_token_expired(expires_at: datetime) -> bool:
    """Check if a token has expired.

    Args:
        expires_at: The expiry datetime of the token

    Returns:
        True if token has expired, False otherwise
    """
    # Ensure expires_at has timezone info
    if expires_at.tzinfo is None:
        # Assume UTC if no timezone info
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) > expires_at


def create_token_info() -> TokenInfo:
    """Create a new token with all necessary information.

    Returns:
        TokenInfo object containing the full token, hash, and prefix
    """
    full_token = generate_pat_token()
    token_hash_value = hash_token(full_token)
    token_prefix = extract_token_prefix(full_token)

    return TokenInfo(
        full_token=full_token,
        token_hash=token_hash_value,
        token_prefix=token_prefix,
    )
