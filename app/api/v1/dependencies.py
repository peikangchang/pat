"""Dependencies for API endpoints (authentication, authorization)."""
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.exceptions import (
    UnauthorizedException,
    ForbiddenException,
    TokenRevokedException,
    TokenExpiredException,
    InvalidTokenException,
)
from app.domain.permissions import has_permission
from app.usecase.auth_usecase import AuthUsecase
from app.models.user import User
from app.models.token import Token


async def get_current_user_from_jwt(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from JWT token.

    Args:
        authorization: Authorization header (Bearer token)
        session: Database session

    Returns:
        User object

    Raises:
        UnauthorizedException: If token is missing or invalid
    """
    # Parse HTTP Authorization header (API layer responsibility)
    if not authorization:
        raise UnauthorizedException("Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedException("Invalid token")

    jwt_token = parts[1]

    # Delegate to usecase (business logic layer)
    auth_usecase = AuthUsecase(session)
    user = await auth_usecase.authenticate_jwt(jwt_token)

    return user


async def get_current_token_from_pat(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> tuple[Token, User]:
    """Get current token and user from PAT.

    Stores token info in request.state for audit logging by middleware.

    Args:
        request: FastAPI request object
        authorization: Authorization header (Bearer token)
        session: Database session

    Returns:
        Tuple of (Token, User)

    Raises:
        UnauthorizedException: If token is missing, invalid, revoked, or expired
    """
    # Parse HTTP Authorization header (API layer responsibility)
    if not authorization:
        raise UnauthorizedException("Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedException("Invalid token")

    pat_token = parts[1]

    # Extract HTTP context information
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    endpoint = str(request.url.path)

    # Pre-populate audit info with request details (token_id will be set if auth succeeds)
    request.state.pat_audit_info = {
        "token_id": None,  # Will be set if token is found
        "ip_address": client_ip,
        "method": method,
        "endpoint": endpoint,
        "session": session,
        "failure_reason": None,  # Will be set if authentication fails
    }

    # Delegate to usecase (business logic layer)
    auth_usecase = AuthUsecase(session)
    try:
        token, user = await auth_usecase.authenticate_pat(
            pat_token=pat_token,
            client_ip=client_ip,
            method=method,
            endpoint=endpoint,
        )
        # Update with token ID on successful authentication
        request.state.pat_audit_info["token_id"] = token.id
        return token, user
    except TokenRevokedException as e:
        # Token was found but is revoked
        await _set_audit_info_for_failed_auth(session, pat_token, "Token revoked", request)
        raise
    except TokenExpiredException as e:
        # Token was found but is expired
        await _set_audit_info_for_failed_auth(session, pat_token, "Token expired", request)
        raise
    except InvalidTokenException as e:
        # Token not found or invalid
        await _set_audit_info_for_failed_auth(session, pat_token, "Invalid token", request)
        raise


async def _set_audit_info_for_failed_auth(
    session: AsyncSession, pat_token: str, reason: str, request: Request
) -> None:
    """Set audit info for failed authentication attempts."""
    from app.domain.token_service import hash_token
    from app.repository.token_repository import TokenRepository

    token_hash = hash_token(pat_token)
    token_repo = TokenRepository(session)

    try:
        async with session.begin():
            _, token = await token_repo.is_valid(token_hash)
            if token:
                request.state.pat_audit_info["token_id"] = token.id
                request.state.pat_audit_info["failure_reason"] = reason
    except Exception:
        # If we can't get the token, just skip audit logging for this request
        pass


def require_permission(required_scope: str):
    """Dependency to check if token has required permission.

    Args:
        required_scope: Required scope (e.g., 'workspacess:read')

    Returns:
        Dependency function
    """

    async def check_permission(
        token_user: Annotated[tuple[Token, User], Depends(get_current_token_from_pat)],
    ) -> tuple[Token, User]:
        """Check if token has required permission."""
        token, user = token_user

        if not has_permission(token.scopes, required_scope):
            raise ForbiddenException(
                message="Insufficient permissions",
                required_scope=required_scope,
                your_scopes=token.scopes,
            )

        return token, user

    return check_permission


# Type aliases for convenience
CurrentUser = Annotated[User, Depends(get_current_user_from_jwt)]
CurrentTokenUser = Annotated[tuple[Token, User], Depends(get_current_token_from_pat)]
