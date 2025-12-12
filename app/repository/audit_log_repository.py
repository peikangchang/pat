"""Audit log repository for database operations."""
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    """Repository for AuditLog model operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        token_id: UUID,
        ip_address: str,
        method: str,
        endpoint: str,
        status_code: int,
        authorized: bool,
        reason: str | None = None,
    ) -> AuditLog:
        """Create a new audit log entry.

        Args:
            token_id: Token UUID
            ip_address: Client IP address
            method: HTTP method
            endpoint: API endpoint
            status_code: HTTP status code
            authorized: Whether request was authorized
            reason: Failure reason (if not authorized)

        Returns:
            Created AuditLog object
        """
        log = AuditLog(
            token_id=token_id,
            ip_address=ip_address,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            authorized=authorized,
            reason=reason,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_by_id(self, log_id: UUID) -> AuditLog | None:
        """Get audit log by ID.

        Args:
            log_id: AuditLog UUID

        Returns:
            AuditLog object if found, None otherwise
        """
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def list_by_token(
        self,
        token_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs for a token.

        Args:
            token_id: Token UUID
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            Tuple of (list of AuditLog objects, total count)
        """
        # Get logs
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.token_id == token_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = list(result.scalars().all())

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.token_id == token_id)
        )
        total = count_result.scalar_one()

        return logs, total

    async def list_by_user_tokens(
        self,
        token_ids: list[UUID],
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs for multiple tokens (useful for user's all tokens).

        Args:
            token_ids: List of Token UUIDs
            limit: Maximum number of logs to return
            offset: Number of logs to skip

        Returns:
            Tuple of (list of AuditLog objects, total count)
        """
        if not token_ids:
            return [], 0

        # Get logs
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.token_id.in_(token_ids))
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = list(result.scalars().all())

        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.token_id.in_(token_ids))
        )
        total = count_result.scalar_one()

        return logs, total

    async def count_by_token(self, token_id: UUID) -> int:
        """Count audit logs for a token.

        Args:
            token_id: Token UUID

        Returns:
            Number of audit log entries
        """
        result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.token_id == token_id)
        )
        return result.scalar_one()

    async def delete_by_token(self, token_id: UUID) -> int:
        """Delete all audit logs for a token.

        Args:
            token_id: Token UUID

        Returns:
            Number of deleted logs
        """
        count = await self.count_by_token(token_id)
        await self.session.execute(
            AuditLog.__table__.delete().where(AuditLog.token_id == token_id)
        )
        await self.session.flush()
        return count
