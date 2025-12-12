"""Pydantic schemas for API request/response."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ===== Auth Schemas =====


class UserRegisterRequest(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v


class UserLoginRequest(BaseModel):
    """User login request."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


# ===== User Schemas =====


class UserResponse(BaseModel):
    """User response."""

    id: UUID
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# ===== PAT Token Schemas =====


class TokenCreateRequest(BaseModel):
    """Request to create a new PAT token."""

    name: str = Field(..., min_length=1, max_length=100, description="Token name")
    scopes: list[str] = Field(..., min_items=1, description="List of permission scopes")
    expires_in_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Days until expiration (30, 90, 365, or custom)",
    )


class TokenCreateResponse(BaseModel):
    """Response after creating a PAT token (includes full token - shown only once)."""

    id: UUID
    name: str
    token: str  # Full token - only returned at creation
    token_prefix: str
    scopes: list[str]
    expires_at: datetime
    created_at: datetime


class TokenListItem(BaseModel):
    """Token item in list (without full token)."""

    id: UUID
    name: str
    token_prefix: str  # Only prefix shown in list
    scopes: list[str]
    expires_at: datetime
    last_used_at: datetime | None
    is_revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenListResponse(BaseModel):
    """List of tokens response."""

    tokens: list[TokenListItem]
    total: int


class TokenDetailResponse(BaseModel):
    """Single token detail response."""

    id: UUID
    name: str
    token_prefix: str
    scopes: list[str]
    expires_at: datetime
    last_used_at: datetime | None
    is_revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Audit Log Schemas =====


class AuditLogItem(BaseModel):
    """Single audit log entry."""

    timestamp: datetime
    ip: str
    method: str
    endpoint: str
    status_code: int
    authorized: bool
    reason: str | None = None


class AuditLogResponse(BaseModel):
    """Audit log response."""

    token_id: UUID
    token_name: str
    total_logs: int
    logs: list[AuditLogItem]


# ===== Resource Access (Stub) Schemas =====


class StubSuccessResponse(BaseModel):
    """Success response for stub endpoints."""

    endpoint: str
    method: str
    required_scope: str
    granted_by: str
    your_scopes: list[str]


# ===== FCS Schemas =====


class FCSParameterResponse(BaseModel):
    """FCS parameter response."""

    index: int
    pnn: str
    pns: str
    range: int
    display: str

    class Config:
        from_attributes = True


class FCSParametersResponse(BaseModel):
    """FCS parameters list response."""

    total_events: int
    total_parameters: int
    parameters: list[FCSParameterResponse]


class FCSEventData(BaseModel):
    """FCS event data (dynamic fields based on parameters)."""

    # This will contain parameter names as keys with their values
    # e.g., {"FSC-H": 2500000, "FSC-A": 2800000, ...}
    pass


class FCSEventsResponse(BaseModel):
    """FCS events response."""

    total_events: int
    limit: int
    offset: int
    events: list[dict]  # List of event data dictionaries


class FCSUploadResponse(BaseModel):
    """FCS file upload response."""

    file_id: str
    filename: str
    total_events: int
    total_parameters: int


class FCSStatisticItem(BaseModel):
    """FCS parameter statistics."""

    parameter: str
    pns: str
    display: str
    min: float
    max: float
    mean: float
    median: float
    std: float


class FCSStatisticsResponse(BaseModel):
    """FCS statistics response."""

    total_events: int
    statistics: list[FCSStatisticItem]
