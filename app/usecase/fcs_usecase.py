"""FCS file usecase for file upload and analysis."""
import os
import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import fcsparser
import numpy as np

from app.common.exceptions import NotFoundException, ForbiddenException, ValidationException
from app.domain.permissions import parse_scope, get_implied_permissions
from app.repository.fcs_repository import FCSRepository


class FCSUsecase:
    """Usecase for FCS file operations."""

    def __init__(self, session: AsyncSession, upload_dir: str = "uploads"):
        self.session = session
        self.fcs_repo = FCSRepository(session)
        self.upload_dir = upload_dir

        # Ensure upload directory exists
        os.makedirs(upload_dir, exist_ok=True)

    def _find_granted_by(self, user_scopes: list[str], required_scope: str) -> str | None:
        """Find which scope granted the required permission."""
        try:
            required_resource, required_permission = parse_scope(required_scope)
        except ValueError:
            return None

        for scope in user_scopes:
            try:
                resource, permission = parse_scope(scope)
            except ValueError:
                continue

            if resource != required_resource:
                continue

            implied_permissions = get_implied_permissions(resource, permission)
            if required_permission in implied_permissions:
                return scope

        return None

    def _generate_file_id(self) -> str:
        """Generate a short random file ID."""
        return secrets.token_urlsafe(8)

    async def upload_file(
        self, user_id: UUID, filename: str, file_content: bytes, scopes: list[str]
    ) -> dict:
        """Upload and parse an FCS file.

        Args:
            user_id: User UUID
            filename: Original filename
            file_content: File content bytes
            scopes: User's granted scopes

        Returns:
            Upload result with file metadata

        Raises:
            ValidationException: If file is invalid
        """
        required_scope = "fcs:write"
        granted_by = self._find_granted_by(scopes, required_scope)

        # Validate filename
        if not filename.lower().endswith('.fcs'):
            raise ValidationException("File must be an FCS file (.fcs extension)")

        # Generate unique file ID
        file_id = self._generate_file_id()
        while await self.fcs_repo.exists_file_id(file_id):
            file_id = self._generate_file_id()

        # Save file to disk
        file_path = os.path.join(self.upload_dir, f"{file_id}.fcs")
        with open(file_path, 'wb') as f:
            f.write(file_content)

        try:
            # Parse FCS file
            meta, data = fcsparser.parse(file_path, reformat_meta=True)

            # Get total events and parameters
            total_events = len(data)
            total_parameters = len(data.columns)

            # Create FCS file record
            fcs_file = await self.fcs_repo.create_file(
                user_id=user_id,
                file_id=file_id,
                filename=filename,
                file_path=file_path,
                total_events=total_events,
                total_parameters=total_parameters,
            )

            # Create parameter records
            for idx, column in enumerate(data.columns, start=1):
                pnn = meta.get(f'$P{idx}N', column)
                pns = meta.get(f'$P{idx}S', column)
                range_val = int(meta.get(f'$P{idx}R', 1024))
                display = meta.get(f'$P{idx}D', 'LIN')

                await self.fcs_repo.create_parameter(
                    file_id=fcs_file.id,
                    index=idx,
                    pnn=pnn,
                    pns=pns,
                    range_value=range_val,
                    display=display,
                )

            return {
                "endpoint": "/api/v1/fcs/upload",
                "method": "POST",
                "required_scope": required_scope,
                "granted_by": granted_by,
                "file_id": file_id,
                "filename": filename,
                "total_events": total_events,
                "total_parameters": total_parameters,
            }

        except Exception as e:
            # Clean up file if parsing fails
            if os.path.exists(file_path):
                os.remove(file_path)
            raise ValidationException(f"Failed to parse FCS file: {str(e)}")

    async def get_parameters(self, user_id: UUID, scopes: list[str]) -> dict:
        """Get FCS file parameters from latest file.

        Args:
            user_id: User UUID
            scopes: User's granted scopes

        Returns:
            Parameter list

        Raises:
            NotFoundException: If no file found
        """
        required_scope = "fcs:read"
        granted_by = self._find_granted_by(scopes, required_scope)

        fcs_file = await self.fcs_repo.get_latest_file_with_parameters(user_id)
        if not fcs_file:
            raise NotFoundException("No FCS file found")

        parameters = [
            {
                "index": param.index,
                "pnn": param.pnn,
                "pns": param.pns,
                "range": param.range,
                "display": param.display,
            }
            for param in fcs_file.parameters
        ]

        return {
            "endpoint": "/api/v1/fcs/parameters",
            "method": "GET",
            "required_scope": required_scope,
            "granted_by": granted_by,
            "total_events": fcs_file.total_events,
            "total_parameters": fcs_file.total_parameters,
            "parameters": parameters,
        }

    async def get_events(
        self, user_id: UUID, scopes: list[str], limit: int = 100, offset: int = 0
    ) -> dict:
        """Get FCS file events (data) from latest file.

        Args:
            user_id: User UUID
            scopes: User's granted scopes
            limit: Max number of events to return
            offset: Number of events to skip

        Returns:
            Event data

        Raises:
            NotFoundException: If no file found
        """
        required_scope = "fcs:read"
        granted_by = self._find_granted_by(scopes, required_scope)

        fcs_file = await self.fcs_repo.get_latest_file(user_id)
        if not fcs_file:
            raise NotFoundException("No FCS file found")

        # Parse FCS file to get events
        _, data = fcsparser.parse(fcs_file.file_path, reformat_meta=True)

        # Get subset of events
        events_subset = data.iloc[offset : offset + limit]

        # Convert to list of dicts
        events = events_subset.to_dict(orient='records')

        return {
            "endpoint": "/api/v1/fcs/events",
            "method": "GET",
            "required_scope": required_scope,
            "granted_by": granted_by,
            "total_events": len(data),
            "limit": limit,
            "offset": offset,
            "events": events,
        }

    async def get_statistics(self, user_id: UUID, scopes: list[str]) -> dict:
        """Get FCS file statistics from latest file.

        Args:
            user_id: User UUID
            scopes: User's granted scopes

        Returns:
            Statistics for all parameters

        Raises:
            NotFoundException: If no file found
        """
        required_scope = "fcs:analyze"
        granted_by = self._find_granted_by(scopes, required_scope)

        fcs_file = await self.fcs_repo.get_latest_file_with_parameters(user_id)
        if not fcs_file:
            raise NotFoundException("No FCS file found")

        # Parse FCS file
        _, data = fcsparser.parse(fcs_file.file_path, reformat_meta=True)

        # Calculate statistics for each parameter
        statistics = []
        for param in fcs_file.parameters:
            column_data = data[data.columns[param.index - 1]]

            statistics.append({
                "parameter": param.pnn,
                "pns": param.pns,
                "display": param.display,
                "min": float(np.min(column_data)),
                "max": float(np.max(column_data)),
                "mean": float(np.mean(column_data)),
                "median": float(np.median(column_data)),
                "std": float(np.std(column_data)),
            })

        return {
            "endpoint": "/api/v1/fcs/statistics",
            "method": "GET",
            "required_scope": required_scope,
            "granted_by": granted_by,
            "total_events": len(data),
            "statistics": statistics,
        }
