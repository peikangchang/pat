"""Authentication usecase for user registration and login."""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    UnauthorizedException,
    ValidationException,
    ServiceUnavailableException,
    InternalServerException,
    TokenExpiredException,
    TokenRevokedException,
    InvalidTokenException,
)
from app.domain.auth_service import hash_password, verify_password, create_access_token, extract_user_id_from_token
from app.domain.token_service import hash_token
from app.domain.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.repository.user_repository import UserRepository
from app.repository.token_repository import TokenRepository
from app.repository.audit_log_repository import AuditLogRepository
from app.repository.exceptions import (
    DuplicateRecordException,
    DatabaseConnectionException,
    DatabaseOperationException,
)
from app.models.user import User
from app.models.token import Token


class AuthUsecase:
    """Usecase for authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = TokenRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def register(self, request: UserRegisterRequest) -> UserResponse:
        """Register a new user.

        Args:
            request: User registration request

        Returns:
            UserResponse with created user info

        Raises:
            ValidationException: If username or email already exists
            ServiceUnavailableException: If database connection fails
            InternalServerException: If database operation fails
        """
        try:
            # Hash password
            password_hash = hash_password(request.password)

            # Create user
            user = await self.user_repo.create(
                username=request.username,
                email=request.email,
                password_hash=password_hash,
            )

            return UserResponse.model_validate(user)

        except DuplicateRecordException as e:
            # Translate repository exception to business exception
            raise ValidationException(e.message)
        except DatabaseConnectionException:
            raise ServiceUnavailableException()
        except DatabaseOperationException:
            raise InternalServerException("Failed to create user")

    async def login(self, request: UserLoginRequest) -> TokenResponse:
        """Authenticate user and return JWT token.

        Args:
            request: User login request

        Returns:
            TokenResponse with JWT access token

        Raises:
            UnauthorizedException: If credentials are invalid
        """
        # Get user by username
        user = await self.user_repo.get_by_username(request.username)
        if not user:
            raise UnauthorizedException("Invalid username or password")

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise UnauthorizedException("Invalid username or password")

        # Create JWT token
        access_token = create_access_token(user.id)

        return TokenResponse(access_token=access_token)

    async def authenticate_jwt(self, jwt_token: str) -> User:
        """Authenticate user from JWT token.

        Args:
            jwt_token: JWT token string

        Returns:
            User object

        Raises:
            UnauthorizedException: If token is invalid or user not found
        """
        # Extract user ID from JWT (domain service)
        user_id = extract_user_id_from_token(jwt_token)
        if not user_id:
            raise UnauthorizedException("Invalid or expired token")

        # Get user from database
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UnauthorizedException("User not found")

        return user

    async def authenticate_pat(
        self,
        pat_token: str,
        client_ip: str,
        method: str,
        endpoint: str,
    ) -> tuple[Token, User]:
        """Authenticate user from PAT token and log access.

        Args:
            pat_token: PAT token string
            client_ip: Client IP address
            method: HTTP method
            endpoint: API endpoint

        Returns:
            Tuple of (Token, User)

        Raises:
            TokenExpiredException: If token has expired
            TokenRevokedException: If token has been revoked
            InvalidTokenException: If token is invalid
            UnauthorizedException: If user not found
        """
        # Hash the token (domain service)
        token_hash = hash_token(pat_token)

        # Validate token (repository)
        is_valid, token = await self.token_repo.is_valid(token_hash)

        if not is_valid or not token:
            # Log failed access if token exists
            if token:
                await self._log_failed_access(token, client_ip, method, endpoint)

                # Raise specific exception based on failure reason
                if token.is_revoked:
                    raise TokenRevokedException()
                elif datetime.now(timezone.utc) > token.expires_at:
                    raise TokenExpiredException()

            raise InvalidTokenException()

        # Get user
        user = await self.user_repo.get_by_id(token.user_id)
        if not user:
            raise UnauthorizedException("User not found")

        # Update last used timestamp
        await self.token_repo.update_last_used(token.id)

        # Log successful access
        await self.audit_repo.create(
            token_id=token.id,
            ip_address=client_ip,
            method=method,
            endpoint=endpoint,
            status_code=200,
            authorized=True,
        )

        return token, user

    async def _log_failed_access(
        self,
        token: Token,
        client_ip: str,
        method: str,
        endpoint: str,
    ) -> None:
        """Log failed PAT access attempt.

        Args:
            token: Token object
            client_ip: Client IP address
            method: HTTP method
            endpoint: API endpoint
        """
        # Determine failure reason
        if token.is_revoked:
            reason = "Token revoked"
        elif datetime.now(timezone.utc) > token.expires_at:
            reason = "Token expired"
        else:
            reason = "Invalid token"

        # Create audit log
        await self.audit_repo.create(
            token_id=token.id,
            ip_address=client_ip,
            method=method,
            endpoint=endpoint,
            status_code=401,
            authorized=False,
            reason=reason,
        )
