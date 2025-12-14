"""FCS (Flow Cytometry Standard) file management API endpoints."""
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.common.rate_limit import limiter
from app.usecase.fcs_usecase import FCSUsecase
from .dependencies import CurrentTokenUser, require_permission

router = APIRouter()


@router.post("/fcs/upload", response_model=dict, dependencies=[Depends(require_permission("fcs:write"))])
@limiter.limit("60/minute")
async def upload_fcs_file(
    request: Request,
    token_user: CurrentTokenUser,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    """Upload and parse an FCS file.

    Requires: fcs:write permission

    Args:
        file: FCS file to upload
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with FCS file metadata
    """
    token, user = token_user
    usecase = FCSUsecase(session)

    # Read file content
    content = await file.read()

    result = await usecase.upload_file(
        user_id=user.id,
        filename=file.filename or "unknown.fcs",
        file_content=content,
        scopes=token.scopes,
    )

    return success_response(result)


@router.get("/fcs/parameters", response_model=dict, dependencies=[Depends(require_permission("fcs:read"))])
@limiter.limit("60/minute")
async def get_fcs_parameters(
    request: Request,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Get FCS file parameters (PnN/PnS) from latest uploaded file.

    Requires: fcs:read permission

    Args:
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with parameters list
    """
    token, user = token_user
    usecase = FCSUsecase(session)
    result = await usecase.get_parameters(user.id, token.scopes)
    return success_response(result)


@router.get("/fcs/events", response_model=dict, dependencies=[Depends(require_permission("fcs:read"))])
@limiter.limit("60/minute")
async def get_fcs_events(
    request: Request,
    token_user: CurrentTokenUser,
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Get FCS file event data from latest uploaded file.

    Requires: fcs:read permission

    Args:
        limit: Maximum number of events to return (1-10000)
        offset: Number of events to skip
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with event data
    """
    token, user = token_user
    usecase = FCSUsecase(session)
    result = await usecase.get_events(user.id, token.scopes, limit=limit, offset=offset)
    return success_response(result)


@router.get("/fcs/statistics", response_model=dict, dependencies=[Depends(require_permission("fcs:analyze"))])
@limiter.limit("60/minute")
async def get_fcs_statistics(
    request: Request,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Get FCS file statistics from latest uploaded file.

    Requires: fcs:analyze permission

    Args:
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with statistics
    """
    token, user = token_user
    usecase = FCSUsecase(session)
    result = await usecase.get_statistics(user.id, token.scopes)
    return success_response(result)
