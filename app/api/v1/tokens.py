"""Token (PAT) management API endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.common.rate_limit import limiter
from app.domain.schemas import TokenCreateRequest
from app.usecase.token_usecase import TokenUsecase
from .dependencies import CurrentUser

router = APIRouter()


@router.post("/tokens", response_model=dict)
@limiter.limit("60/minute")
async def create_token(
    request: Request,
    token_request: TokenCreateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
):
    """Create a new PAT token.

    Args:
        request: FastAPI Request object (for rate limiting)
        token_request: Token creation request
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success response with token info (includes full token, shown only once)
    """
    usecase = TokenUsecase(session)
    token = await usecase.create_token(current_user.id, token_request)
    return success_response(token.model_dump())


@router.get("/tokens", response_model=dict)
async def list_tokens(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
):
    """List all tokens for current user.

    Args:
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success response with list of tokens (without full token)
    """
    usecase = TokenUsecase(session)
    tokens = await usecase.list_tokens(current_user.id)
    return success_response(tokens.model_dump())


@router.get("/tokens/{token_id}", response_model=dict)
async def get_token(
    token_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
):
    """Get token details.

    Args:
        token_id: Token UUID
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success response with token details
    """
    usecase = TokenUsecase(session)
    token = await usecase.get_token(current_user.id, token_id)
    return success_response(token.model_dump())


@router.delete("/tokens/{token_id}", response_model=dict)
async def revoke_token(
    token_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_db),
):
    """Revoke a token.

    Args:
        token_id: Token UUID
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success response with revoked token details
    """
    usecase = TokenUsecase(session)
    token = await usecase.revoke_token(current_user.id, token_id)
    return success_response(token.model_dump())


@router.get("/tokens/{token_id}/logs", response_model=dict)
async def get_token_logs(
    token_id: UUID,
    current_user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Get audit logs for a token.

    Args:
        token_id: Token UUID
        current_user: Current authenticated user
        limit: Maximum number of logs to return (1-1000)
        offset: Number of logs to skip
        session: Database session

    Returns:
        Success response with audit logs
    """
    usecase = TokenUsecase(session)
    logs = await usecase.get_token_logs(current_user.id, token_id, limit=limit, offset=offset)
    return success_response(logs)
