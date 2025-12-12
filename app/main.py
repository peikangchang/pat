import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from app.common.config import settings
from app.common.database import init_db, close_db
from app.common.exceptions import AppException
from app.common.responses import error_response

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
    response_data = error_response(
        error=exc.__class__.__name__.replace("Exception", ""),
        message=exc.message
    )

    # Add retry_after for rate limit exceptions
    if hasattr(exc, 'retry_after'):
        response_data["data"] = {"retry_after": exc.retry_after}

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


# Import and include routers (will be added later)
# from app.api.v1 import auth, tokens, workspaces, users, fcs
# app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
# app.include_router(tokens.router, prefix="/api/v1", tags=["tokens"])
# app.include_router(workspaces.router, prefix="/api/v1", tags=["workspaces"])
# app.include_router(users.router, prefix="/api/v1", tags=["users"])
# app.include_router(fcs.router, prefix="/api/v1", tags=["fcs"])
