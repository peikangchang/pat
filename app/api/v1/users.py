"""User management API endpoints."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.common.rate_limit import limiter, RATE_LIMIT
from app.usecase.user_usecase import UserUsecase
from .dependencies import CurrentTokenUser, require_permission

router = APIRouter()


@router.get("/users/me", response_model=dict, dependencies=[Depends(require_permission("users:read"))])
@limiter.limit(RATE_LIMIT)
async def get_current_user(
    request: Request,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Get current user information.

    Requires: users:read permission

    Args:
        token_user: Current token and user (from PAT)
        session: Database session

    Returns:
        Success response with user info
    """
    token, user = token_user
    usecase = UserUsecase()
    result = await usecase.get_current_user(str(user.id), token.scopes)
    return success_response(result)


@router.put("/users/me", response_model=dict, dependencies=[Depends(require_permission("users:write"))])
@limiter.limit(RATE_LIMIT)
async def update_current_user(
    request: Request,
    token_user: CurrentTokenUser,
    session: AsyncSession = Depends(get_db),
):
    """Update current user information.

    Requires: users:write permission

    Args:
        token_user: Current token and user (from PAT)
        session: Database session

    Returns:
        Success response with update result
    """
    token, user = token_user
    usecase = UserUsecase()
    result = await usecase.update_user(str(user.id), token.scopes)
    return success_response(result)
