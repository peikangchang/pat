"""Authentication API endpoints."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.common.rate_limit import limiter
from app.domain.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.usecase.auth_usecase import AuthUsecase

router = APIRouter()


@router.post("/auth/register", response_model=dict)
@limiter.limit("60/minute")
async def register(
    request: Request,
    user_request: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    """Register a new user.

    Args:
        request: FastAPI Request object (for rate limiting)
        user_request: User registration request
        session: Database session

    Returns:
        Success response with user info
    """
    usecase = AuthUsecase(session)
    user = await usecase.register(user_request)
    return success_response(user.model_dump())


@router.post("/auth/login", response_model=dict)
@limiter.limit("60/minute")
async def login(
    request: Request,
    login_request: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Login and get JWT access token.

    Args:
        request: FastAPI Request object (for rate limiting)
        login_request: User login request
        session: Database session

    Returns:
        Success response with access token
    """
    usecase = AuthUsecase(session)
    token = await usecase.login(login_request)
    return success_response(token.model_dump())
