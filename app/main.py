import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.common.config import settings
from app.common.database import init_db, close_db, async_session_maker
from app.common.exceptions import AppException, UnauthorizedException
from app.common.responses import error_response
from app.common.rate_limit import limiter
from app.common.audit_middleware import AuditLogMiddleware
from app.common.startup import initialize_sample_fcs_file


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()

    # Initialize sample FCS file if needed
    async with async_session_maker() as session:
        await initialize_sample_fcs_file(session)

    yield

    # Shutdown
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Custom rate limit exceeded handler
def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors.

    Calculates actual retry-after time from rate limit window statistics
    and formats response according to design document.
    """
    import time

    # Get limiter from app state
    limiter_instance = request.app.state.limiter

    # Get the rate limit that was exceeded from request state
    # This is set by the @limiter.limit() decorator
    view_rate_limit = getattr(request.state, "view_rate_limit", None)

    # Calculate actual retry-after time
    if view_rate_limit:
        # Get window statistics from limiter
        window_stats = limiter_instance.limiter.get_window_stats(
            view_rate_limit[0], *view_rate_limit[1]
        )
        # Calculate reset time: reset_in is the absolute timestamp
        reset_in = 1 + window_stats[0]
        # Calculate seconds until reset
        retry_after = int(reset_in - time.time())
        # Ensure non-negative value
        retry_after = max(1, retry_after)
    else:
        # Fallback to default if view_rate_limit not available
        retry_after = 60

    # Return response in design document format
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "success": False,
            "error": "Too Many Requests",
            "data": {
                "retry_after": retry_after
            }
        },
        headers={"Retry-After": str(retry_after)},
    )

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Add SlowAPI middleware to enable rate limiting
app.add_middleware(SlowAPIMiddleware)

# Add audit logging middleware (must be before other middlewares)
app.add_middleware(AuditLogMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    # For UnauthorizedException and its subclasses, always use "Unauthorized" as error type
    if isinstance(exc, UnauthorizedException):
        error_type = "Unauthorized"
    else:
        error_type = exc.__class__.__name__.replace("Exception", "")

    response_data = error_response(
        error=error_type,
        message=exc.message
    )

    # Add retry_after for rate limit exceptions
    if hasattr(exc, 'retry_after'):
        response_data["data"] = {"retry_after": exc.retry_after}

    # Add permission details for forbidden exceptions
    if hasattr(exc, 'required_scope') and exc.required_scope:
        response_data["data"] = {
            "required_scope": exc.required_scope,
            "your_scopes": exc.your_scopes,
        }

    return JSONResponse(
        status_code=exc.status_code,
        content=response_data,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            error="InternalServerError",
            message=str(exc) if settings.debug else "An error occurred"
        ),
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers
from app.api.v1 import auth, tokens, workspaces, users, fcs

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(tokens.router, prefix="/api/v1", tags=["tokens"])
app.include_router(workspaces.router, prefix="/api/v1", tags=["workspaces"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(fcs.router, prefix="/api/v1", tags=["fcs"])
