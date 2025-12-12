"""User repository for database operations."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from app.models.user import User
from .exceptions import (
    DuplicateRecordException,
    DatabaseConnectionException,
    DatabaseOperationException,
)


class UserRepository:
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, username: str, email: str, password_hash: str) -> User:
        """Create a new user.

        Args:
            username: Username
            email: Email address
            password_hash: Hashed password

        Returns:
            Created User object

        Raises:
            DuplicateRecordException: If username or email already exists
            DatabaseConnectionException: If database connection fails
            DatabaseOperationException: If database operation fails
        """
        try:
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
            )
            self.session.add(user)
            await self.session.flush()
            await self.session.refresh(user)
            return user
        except IntegrityError as e:
            error_msg = str(e.orig).lower()
            if "unique" in error_msg:
                if "username" in error_msg:
                    raise DuplicateRecordException(f"Username '{username}' already exists")
                elif "email" in error_msg:
                    raise DuplicateRecordException(f"Email '{email}' already exists")
                raise DuplicateRecordException("User already exists")
            raise DatabaseOperationException("Failed to create user", detail=str(e.orig))
        except OperationalError as e:
            raise DatabaseConnectionException(detail=str(e.orig))
        except DBAPIError as e:
            raise DatabaseOperationException(detail=str(e.orig))

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: Email address

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def exists_by_username(self, username: str) -> bool:
        """Check if username already exists.

        Args:
            username: Username to check

        Returns:
            True if exists, False otherwise
        """
        user = await self.get_by_username(username)
        return user is not None

    async def exists_by_email(self, email: str) -> bool:
        """Check if email already exists.

        Args:
            email: Email to check

        Returns:
            True if exists, False otherwise
        """
        user = await self.get_by_email(email)
        return user is not None

    async def update_password(self, user_id: UUID, new_password_hash: str) -> User | None:
        """Update user's password.

        Args:
            user_id: User UUID
            new_password_hash: New hashed password

        Returns:
            Updated User object if found, None otherwise
        """
        user = await self.get_by_id(user_id)
        if user:
            user.password_hash = new_password_hash
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def delete(self, user_id: UUID) -> bool:
        """Delete a user.

        Args:
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(user_id)
        if user:
            await self.session.delete(user)
            await self.session.flush()
            return True
        return False
