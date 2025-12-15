"""Workspace management API endpoints."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.common.rate_limit import limiter, RATE_LIMIT
from app.usecase.workspace_usecase import WorkspaceUsecase
from .dependencies import CurrentTokenUser, require_permission

router = APIRouter()


@router.get("/workspacess", response_model=dict, dependencies=[Depends(require_permission("workspacess:read"))])
@limiter.shared_limit(RATE_LIMIT, scope="global")
async def list_workspaces(
    request: Request,
    token_user: CurrentTokenUser,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List all workspaces accessible by the token.

    Requires: workspacess:read permission

    Args:
        token_user: Current token and user
        limit: Maximum number of workspaces to return (1-1000)
        offset: Number of workspaces to skip
        session: Database session

    Returns:
        Success response with list of workspaces
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.list_workspaces(token.scopes)
    return success_response(result)


@router.post("/workspacess", response_model=dict, dependencies=[Depends(require_permission("workspacess:write"))])
@limiter.shared_limit(RATE_LIMIT, scope="global")
async def create_workspace(
    request: Request,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Create a new workspace.

    Requires: workspacess:write permission

    Args:
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with created workspace
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.create_workspace(token.scopes)
    return success_response(result)


@router.delete("/workspacess/{id}", response_model=dict, dependencies=[Depends(require_permission("workspacess:delete"))])
@limiter.shared_limit(RATE_LIMIT, scope="global")
async def delete_workspace(
    request: Request,
    id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Delete a workspace.

    Requires: workspacess:delete permission

    Args:
        id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.delete_workspace(id, token.scopes)
    return success_response(result)


@router.put("/workspacess/{id}/settings", response_model=dict, dependencies=[Depends(require_permission("workspacess:admin"))])
@limiter.shared_limit(RATE_LIMIT, scope="global")
async def update_workspace_settings(
    request: Request,
    id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Update workspace settings.

    Requires: workspacess:admin permission

    Args:
        id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with settings
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.update_workspace_settings(id, token.scopes)
    return success_response(result)
