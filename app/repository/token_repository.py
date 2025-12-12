"""Token repository for database operations."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from app.models.token import Token
from .exceptions import (
    DuplicateRecordException,
    DatabaseConnectionException,
    DatabaseOperationException,
)


class TokenRepository:
    """Repository for Token model operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        token_hash: str,
        token_prefix: str,
        scopes: list[str],
        expires_at: datetime,
    ) -> Token:
        """Create a new token.

        Args:
            user_id: User UUID
            name: Token name
            token_hash: SHA-256 hash of the token
            token_prefix: Token prefix for display
            scopes: List of permission scopes
            expires_at: Expiration datetime

        Returns:
            Created Token object

        Raises:
            DuplicateRecordException: If token hash already exists
            DatabaseConnectionException: If database connection fails
            DatabaseOperationException: If database operation fails
        """
        try:
            token = Token(
                user_id=user_id,
                name=name,
                token_hash=token_hash,
                token_prefix=token_prefix,
                scopes=scopes,
                expires_at=expires_at,
            )
            self.session.add(token)
            await self.session.flush()
            await self.session.refresh(token)
            return token
        except IntegrityError as e:
            error_msg = str(e.orig).lower()
            if "unique" in error_msg and "token_hash" in error_msg:
                raise DuplicateRecordException("Token hash collision detected")
            raise DatabaseOperationException("Failed to create token", detail=str(e.orig))
        except OperationalError as e:
            raise DatabaseConnectionException(detail=str(e.orig))
        except DBAPIError as e:
            raise DatabaseOperationException(detail=str(e.orig))

    async def get_by_id(self, token_id: UUID) -> Token | None:
        """Get token by ID.

        Args:
            token_id: Token UUID

        Returns:
            Token object if found, None otherwise
        """
        result = await self.session.execute(
            select(Token).where(Token.id == token_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, token_hash: str) -> Token | None:
        """Get token by hash.

        Args:
            token_hash: Token hash

        Returns:
            Token object if found, None otherwise
        """
        result = await self.session.execute(
            select(Token).where(Token.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_prefix(self, token_prefix: str) -> list[Token]:
        """Get tokens by prefix.

        Args:
            token_prefix: Token prefix

        Returns:
            List of Token objects
        """
        result = await self.session.execute(
            select(Token).where(Token.token_prefix == token_prefix)
        )
        return list(result.scalars().all())

    async def list_by_user(self, user_id: UUID) -> list[Token]:
        """List all tokens for a user.

        Args:
            user_id: User UUID

        Returns:
            List of Token objects
        """
        result = await self.session.execute(
            select(Token)
            .where(Token.user_id == user_id)
            .order_by(Token.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_by_user(self, user_id: UUID) -> list[Token]:
        """List all active (not revoked, not expired) tokens for a user.

        Args:
            user_id: User UUID

        Returns:
            List of active Token objects
        """
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Token)
            .where(
                and_(
                    Token.user_id == user_id,
                    Token.is_revoked == False,
                    Token.expires_at > now,
                )
            )
            .order_by(Token.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, token_id: UUID) -> Token | None:
        """Revoke a token.

        Args:
            token_id: Token UUID

        Returns:
            Revoked Token object if found, None otherwise
        """
        token = await self.get_by_id(token_id)
        if token:
            token.is_revoked = True
            await self.session.flush()
            await self.session.refresh(token)
        return token

    async def update_last_used(self, token_id: UUID) -> Token | None:
        """Update token's last used timestamp.

        Args:
            token_id: Token UUID

        Returns:
            Updated Token object if found, None otherwise
        """
        token = await self.get_by_id(token_id)
        if token:
            token.last_used_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.session.refresh(token)
        return token

    async def delete(self, token_id: UUID) -> bool:
        """Delete a token.

        Args:
            token_id: Token UUID

        Returns:
            True if deleted, False if not found
        """
        token = await self.get_by_id(token_id)
        if token:
            await self.session.delete(token)
            await self.session.flush()
            return True
        return False

    async def is_valid(self, token_hash: str) -> tuple[bool, Token | None]:
        """Check if a token is valid (exists, not revoked, not expired).

        Args:
            token_hash: Token hash to check

        Returns:
            Tuple of (is_valid, token_object)
        """
        token = await self.get_by_hash(token_hash)
        if not token:
            return False, None

        if token.is_revoked:
            return False, token

        if datetime.now(timezone.utc) > token.expires_at:
            return False, token

        return True, token
