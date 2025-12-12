"""Authentication API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.database import get_db
from app.common.responses import success_response
from app.domain.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.usecase.auth_usecase import AuthUsecase

router = APIRouter()


@router.post("/auth/register", response_model=dict)
async def register(
    request: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
):
    """Register a new user.

    Args:
        request: User registration request
        session: Database session

    Returns:
        Success response with user info
    """
    usecase = AuthUsecase(session)
    user = await usecase.register(request)
    return success_response(user.model_dump())


@router.post("/auth/login", response_model=dict)
async def login(
    request: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
):
    """Login and get JWT access token.

    Args:
        request: User login request
        session: Database session

    Returns:
        Success response with access token
    """
    usecase = AuthUsecase(session)
    token = await usecase.login(request)
    return success_response(token.model_dump())
