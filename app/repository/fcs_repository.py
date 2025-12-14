"""FCS file repository for database operations."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fcs import FCSFile, FCSParameter


class FCSRepository:
    """Repository for FCS file model operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_file(
        self,
        filename: str,
        file_path: str,
        total_events: int,
        total_parameters: int,
    ) -> FCSFile:
        """Create a new FCS file record (globally shared).

        Args:
            filename: Original filename
            file_path: Path to stored file
            total_events: Number of events in file
            total_parameters: Number of parameters in file

        Returns:
            Created FCSFile object
        """
        fcs_file = FCSFile(
            filename=filename,
            file_path=file_path,
            total_events=total_events,
            total_parameters=total_parameters,
        )
        self.session.add(fcs_file)
        await self.session.flush()
        await self.session.refresh(fcs_file)
        return fcs_file

    async def create_parameter(
        self,
        file_id: UUID,
        index: int,
        pnn: str,
        pns: str,
        range_value: int,
        display: str,
    ) -> FCSParameter:
        """Create a new FCS parameter record.

        Args:
            file_id: FCSFile UUID
            index: Parameter index
            pnn: Parameter name
            pns: Parameter short name
            range_value: Parameter range
            display: Display type (LIN or LOG)

        Returns:
            Created FCSParameter object
        """
        parameter = FCSParameter(
            file_id=file_id,
            index=index,
            pnn=pnn,
            pns=pns,
            range=range_value,
            display=display,
        )
        self.session.add(parameter)
        await self.session.flush()
        await self.session.refresh(parameter)
        return parameter

    async def get_file_by_id(self, fcs_file_id: UUID) -> FCSFile | None:
        """Get FCS file by UUID.

        Args:
            fcs_file_id: FCSFile UUID

        Returns:
            FCSFile object if found, None otherwise
        """
        result = await self.session.execute(
            select(FCSFile).where(FCSFile.id == fcs_file_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_file(self) -> FCSFile | None:
        """Get the latest (and only) FCS file in the system.

        Returns:
            Latest FCSFile object if found, None otherwise
        """
        result = await self.session.execute(
            select(FCSFile)
            .order_by(FCSFile.uploaded_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_file_with_parameters(self) -> FCSFile | None:
        """Get the latest (and only) FCS file in the system with parameters.

        Returns:
            Latest FCSFile object with parameters loaded, None if not found
        """
        result = await self.session.execute(
            select(FCSFile)
            .options(selectinload(FCSFile.parameters))
            .order_by(FCSFile.uploaded_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_parameters_by_file(self, fcs_file_id: UUID) -> list[FCSParameter]:
        """Get all parameters for a file.

        Args:
            fcs_file_id: FCSFile UUID

        Returns:
            List of FCSParameter objects ordered by index
        """
        result = await self.session.execute(
            select(FCSParameter)
            .where(FCSParameter.file_id == fcs_file_id)
            .order_by(FCSParameter.index)
        )
        return list(result.scalars().all())

    async def delete_file(self, fcs_file_id: UUID) -> bool:
        """Delete an FCS file (parameters will be cascade deleted).

        Args:
            fcs_file_id: FCSFile UUID

        Returns:
            True if deleted, False if not found
        """
        fcs_file = await self.get_file_by_id(fcs_file_id)
        if fcs_file:
            await self.session.delete(fcs_file)
            await self.session.flush()
            return True
        return False

