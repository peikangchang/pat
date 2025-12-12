"""Workspace management API endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.usecase.workspace_usecase import WorkspaceUsecase
from .dependencies import CurrentTokenUser, require_permission

router = APIRouter()


@router.get("/workspaces", response_model=dict, dependencies=[Depends(require_permission("workspaces:read"))])
async def list_workspaces(
    token_user: CurrentTokenUser,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """List all workspaces accessible by the token.

    Requires: workspaces:read permission

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


@router.get("/workspaces/{workspace_id}", response_model=dict, dependencies=[Depends(require_permission("workspaces:read"))])
async def get_workspace(
    workspace_id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Get workspace details.

    Requires: workspaces:read permission

    Args:
        workspace_id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with workspace details
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.get_workspace(workspace_id, token.scopes)
    return success_response(result)


@router.put("/workspaces/{workspace_id}", response_model=dict, dependencies=[Depends(require_permission("workspaces:write"))])
async def update_workspace(
    workspace_id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Update a workspace.

    Requires: workspaces:write permission

    Args:
        workspace_id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with update result
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.update_workspace(workspace_id, token.scopes)
    return success_response(result)


@router.delete("/workspaces/{workspace_id}", response_model=dict, dependencies=[Depends(require_permission("workspaces:delete"))])
async def delete_workspace(
    workspace_id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Delete a workspace.

    Requires: workspaces:delete permission

    Args:
        workspace_id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.delete_workspace(workspace_id, token.scopes)
    return success_response(result)


@router.put("/workspaces/{workspace_id}/settings", response_model=dict, dependencies=[Depends(require_permission("workspaces:admin"))])
async def update_workspace_settings(
    workspace_id: str,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Update workspace settings.

    Requires: workspaces:admin permission

    Args:
        workspace_id: Workspace ID
        token_user: Current token and user
        session: Database session

    Returns:
        Success response with settings
    """
    token, user = token_user
    usecase = WorkspaceUsecase()
    result = await usecase.update_workspace_settings(workspace_id, token.scopes)
    return success_response(result)
