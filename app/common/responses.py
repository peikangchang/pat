"""Standard API response formats."""
from typing import Any
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    data: Any


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    message: str | None = None
    data: dict[str, Any] | None = None


def success_response(data: Any) -> dict[str, Any]:
    """Create a success response."""
    return {"success": True, "data": data}


def error_response(
    error: str,
    message: str | None = None,
    data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create an error response."""
    response = {"success": False, "error": error}
    if message:
        response["message"] = message
    if data:
        response["data"] = data
    return response
