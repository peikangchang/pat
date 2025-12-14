"""Authentication service for password hashing and JWT."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from pydantic import BaseModel

from app.common.config import settings


# Argon2 password hasher
ph = PasswordHasher()


class JWTPayload(BaseModel):
    """JWT token payload."""

    sub: str  # Subject (user_id)
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp


def hash_password(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed_password: The hashed password to check against

    Returns:
        True if password matches, False otherwise
    """
    try:
        ph.verify(hashed_password, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be updated.

    This is useful when Argon2 parameters change.

    Args:
        hashed_password: The hashed password to check

    Returns:
        True if hash needs updating, False otherwise
    """
    try:
        return ph.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True


def create_access_token(user_id: UUID, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's UUID
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = JWTPayload(
        sub=str(user_id),
        exp=int(expire.timestamp()),
        iat=int(now.timestamp()),
    )

    encoded_jwt = jwt.encode(
        payload.model_dump(),
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return encoded_jwt


def decode_access_token(token: str) -> JWTPayload | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string

    Returns:
        JWTPayload if valid, None if invalid or expired

    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidTokenError: If token is invalid
    """
    try:
        payload_dict = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return JWTPayload(**payload_dict)
    except jwt.ExpiredSignatureError:
        # Re-raise to let caller handle expired tokens specifically
        raise
    except jwt.InvalidTokenError:
        # Re-raise to let caller handle invalid tokens specifically
        raise


def extract_user_id_from_token(token: str) -> UUID | None:
    """Extract user ID from a JWT token.

    Args:
        token: The JWT token string

    Returns:
        User UUID if valid, None otherwise

    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidTokenError: If token is invalid
    """
    payload = decode_access_token(token)

    try:
        return UUID(payload.sub)
    except (ValueError, AttributeError):
        # Invalid UUID format
        raise jwt.InvalidTokenError("Invalid token payload")
