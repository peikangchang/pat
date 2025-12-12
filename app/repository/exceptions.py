"""Repository layer exceptions.

These exceptions are raised by repositories when database operations fail.
They should be caught and translated to AppExceptions by the usecase layer.
"""


class RepositoryException(Exception):
    """Base exception for repository layer errors."""
    pass


class DuplicateRecordException(RepositoryException):
    """Raised when trying to create a duplicate record (unique constraint violation)."""
    def __init__(self, message: str = "Record already exists", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class DatabaseConnectionException(RepositoryException):
    """Raised when database connection fails."""
    def __init__(self, message: str = "Database connection error", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class ForeignKeyViolationException(RepositoryException):
    """Raised when foreign key constraint is violated."""
    def __init__(self, message: str = "Referenced record does not exist", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class DatabaseOperationException(RepositoryException):
    """Raised when a database operation fails."""
    def __init__(self, message: str = "Database operation failed", detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)
