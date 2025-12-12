"""Custom exceptions for the application."""


class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UnauthorizedException(AppException):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenException(AppException):
    """Raised when user lacks required permissions."""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class NotFoundException(AppException):
    """Raised when resource is not found."""
    def __init__(self, message: str = "Not Found"):
        super().__init__(message, status_code=404)


class ValidationException(AppException):
    """Raised when validation fails."""
    def __init__(self, message: str = "Validation Error"):
        super().__init__(message, status_code=422)


class RateLimitException(AppException):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str = "Too Many Requests", retry_after: int = 60):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class TokenExpiredException(UnauthorizedException):
    """Raised when token has expired."""
    def __init__(self):
        super().__init__("Token expired")


class TokenRevokedException(UnauthorizedException):
    """Raised when token has been revoked."""
    def __init__(self):
        super().__init__("Token revoked")


class InvalidTokenException(UnauthorizedException):
    """Raised when token is invalid."""
    def __init__(self):
        super().__init__("Invalid token")


class ServiceUnavailableException(AppException):
    """Raised when service is temporarily unavailable (e.g., database connection failure)."""
    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, status_code=503)


class InternalServerException(AppException):
    """Raised when an internal server error occurs."""
    def __init__(self, message: str = "Internal server error"):
        super().__init__(message, status_code=500)
