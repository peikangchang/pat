"""Application startup initialization."""
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.fcs_repository import FCSRepository
from app.usecase.fcs_usecase import FCSUsecase

logger = logging.getLogger(__name__)


async def initialize_sample_fcs_file(session: AsyncSession) -> None:
    """Initialize sample FCS file if no files exist.

    Uses the existing FCSUsecase.upload_file() to reuse all validation
    and processing logic.

    Args:
        session: Database session
    """
    try:
        # Check if any FCS files exist
        fcs_repo = FCSRepository(session)
        async with session.begin():
            existing_file = await fcs_repo.get_latest_file()

        if existing_file:
            logger.info(f"FCS file already exists: {existing_file.filename}")
            return

        # Load sample FCS file
        sample_file_path = Path(__file__).parent.parent.parent / "sample_data" / "sample.fcs"

        if not sample_file_path.exists():
            logger.warning(f"Sample FCS file not found at {sample_file_path}")
            return

        logger.info(f"Initializing sample FCS file from {sample_file_path}")

        with open(sample_file_path, 'rb') as f:
            file_content = f.read()

        # Use existing usecase with system-level scopes to reuse all logic
        usecase = FCSUsecase(session)
        system_scopes = ["fcs:write"]  # System initialization has write permission

        result = await usecase.upload_file(
            filename="sample.fcs",
            file_content=file_content,
            scopes=system_scopes,
        )

        logger.info(
            f"Sample FCS file initialized: "
            f"{result['total_events']} events, {result['total_parameters']} parameters"
        )

    except Exception as e:
        logger.error(f"Error initializing sample FCS file: {e}")
        # Don't raise - startup should continue even if sample file fails
