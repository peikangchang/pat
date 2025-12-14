"""Token usecase for PAT management."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    ServiceUnavailableException,
    InternalServerException,
)
from app.domain.permissions import validate_scopes
from app.domain.token_service import create_token_info, calculate_expiry_date
from app.repository.exceptions import (
    DuplicateRecordException,
    DatabaseConnectionException,
    DatabaseOperationException,
)
from app.domain.schemas import (
    TokenCreateRequest,
    TokenCreateResponse,
    TokenListResponse,
    TokenListItem,
    TokenDetailResponse,
)
from app.repository.token_repository import TokenRepository
from app.repository.audit_log_repository import AuditLogRepository


class TokenUsecase:
    """Usecase for PAT token operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.token_repo = TokenRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def create_token(
        self, user_id: UUID, request: TokenCreateRequest
    ) -> TokenCreateResponse:
        """Create a new PAT token.

        Args:
            user_id: User UUID
            request: Token creation request

        Returns:
            TokenCreateResponse with full token (shown only once)

        Raises:
            ValidationException: If scopes are invalid
        """
        # Validate scopes (no DB operation)
        valid, invalid_scopes = validate_scopes(request.scopes)
        if not valid:
            raise ValidationException(
                f"Invalid scopes: {', '.join(invalid_scopes)}"
            )

        # Calculate expiry (no DB operation)
        expires_at = calculate_expiry_date(request.expires_in_days)

        # Retry token generation if hash collision occurs (extremely rare)
        max_retries = 3
        token = None
        token_info = None

        for attempt in range(max_retries):
            # Generate token (no DB operation)
            token_info = create_token_info()

            try:
                # Create token in database (DB operation in transaction)
                async with self.session.begin():
                    token = await self.token_repo.create(
                        user_id=user_id,
                        name=request.name,
                        token_hash=token_info.token_hash,
                        token_prefix=token_info.token_prefix,
                        scopes=request.scopes,
                        expires_at=expires_at,
                    )
                    # Auto-commit on success
                break  # Success, exit retry loop
            except DuplicateRecordException:
                # Hash collision detected (extremely rare), auto-rollback
                if attempt == max_retries - 1:
                    raise ValidationException(
                        "Failed to generate unique token after multiple attempts"
                    )
                # Retry with new token
                continue
            except DatabaseConnectionException:
                # Auto-rollback
                raise ServiceUnavailableException()
            except DatabaseOperationException:
                # Auto-rollback
                raise InternalServerException("Failed to create token")

        if not token or not token_info:
            raise InternalServerException("Failed to create token")

        return TokenCreateResponse(
            id=token.id,
            name=token.name,
            token=token_info.full_token,  # Only returned here
            token_prefix=token.token_prefix,
            scopes=token.scopes,
            expires_at=token.expires_at,
            created_at=token.created_at,
        )

    async def list_tokens(self, user_id: UUID) -> TokenListResponse:
        """List all tokens for a user.

        Args:
            user_id: User UUID

        Returns:
            TokenListResponse with list of tokens (without full token)
        """
        # Get tokens from database (DB operation in transaction)
        async with self.session.begin():
            tokens = await self.token_repo.list_by_user(user_id)

        # Transform to response (no DB operation)
        token_items = [TokenListItem.model_validate(token) for token in tokens]

        return TokenListResponse(
            tokens=token_items,
            total=len(token_items),
        )

    async def get_token(self, user_id: UUID, token_id: UUID) -> TokenDetailResponse:
        """Get token details.

        Args:
            user_id: User UUID
            token_id: Token UUID

        Returns:
            TokenDetailResponse

        Raises:
            NotFoundException: If token not found
            ForbiddenException: If token doesn't belong to user
        """
        # Get token from database (DB operation in transaction)
        async with self.session.begin():
            token = await self.token_repo.get_by_id(token_id)

        # Validate ownership (no DB operation)
        if not token:
            raise NotFoundException("Token not found")

        if token.user_id != user_id:
            raise ForbiddenException("Access denied to this token")

        return TokenDetailResponse.model_validate(token)

    async def revoke_token(self, user_id: UUID, token_id: UUID) -> TokenDetailResponse:
        """Revoke a token.

        Args:
            user_id: User UUID
            token_id: UUID

        Returns:
            TokenDetailResponse

        Raises:
            NotFoundException: If token not found
            ForbiddenException: If token doesn't belong to user
        """
        # Get token and revoke in same transaction (both are DB operations)
        async with self.session.begin():
            token = await self.token_repo.get_by_id(token_id)

            if not token:
                raise NotFoundException("Token not found")

            if token.user_id != user_id:
                raise ForbiddenException("Access denied to this token")

            revoked_token = await self.token_repo.revoke(token_id)
            # Auto-commit on success

        return TokenDetailResponse.model_validate(revoked_token)

    async def get_token_logs(
        self, user_id: UUID, token_id: UUID, limit: int = 100, offset: int = 0
    ):
        """Get audit logs for a token.

        Args:
            user_id: User UUID
            token_id: Token UUID
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            Dict with token info and logs

        Raises:
            NotFoundException: If token not found
            ForbiddenException: If token doesn't belong to user
        """
        # Get token and logs in transaction (all DB operations)
        async with self.session.begin():
            token = await self.token_repo.get_by_id(token_id)

            if not token:
                raise NotFoundException("Token not found")

            if token.user_id != user_id:
                raise ForbiddenException("Access denied to this token")

            logs, total = await self.audit_repo.list_by_token(token_id, limit=limit, offset=offset)

        # Format response (no DB operation)
        return {
            "token_id": token.id,
            "token_name": token.name,
            "total_logs": total,
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "ip": log.ip_address,
                    "method": log.method,
                    "endpoint": log.endpoint,
                    "status_code": log.status_code,
                    "authorized": log.authorized,
                    "reason": log.reason,
                }
                for log in logs
            ],
        }

    async def log_token_usage(
        self,
        token_id: UUID,
        ip_address: str,
        method: str,
        endpoint: str,
        status_code: int,
        authorized: bool,
        reason: str | None = None,
    ):
        """Log token usage to audit log.

        Uses the same session but in an independent transaction block.
        This ensures audit log is persisted regardless of the main transaction outcome.

        Args:
            token_id: Token UUID
            ip_address: Client IP address
            method: HTTP method
            endpoint: API endpoint
            status_code: Final HTTP response status code
            authorized: Whether the request was authorized (2xx status)
            reason: Optional reason for failure
        """
        try:
            # Use session.begin() to start a new, independent transaction
            # This won't commit any pending operations from previous transactions
            async with self.session.begin():
                await self.audit_repo.create(
                    token_id=token_id,
                    ip_address=ip_address,
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    authorized=authorized,
                    reason=reason,
                )
                # Automatically commits on successful exit from context
        except Exception:
            # Automatically rolls back on exception
            # Don't let audit logging errors affect the response
            # Just silently fail (could log to application logs in production)
            pass
