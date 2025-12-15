"""Middleware for audit logging of PAT token usage."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.usecase.token_usecase import TokenUsecase


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to log PAT token usage with final response status.

    This middleware checks if a request used PAT authentication and logs
    the audit entry after the response is generated, ensuring accurate
    status code and authorization result.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and log audit entry after response."""
        # Process the request and get response
        response = await call_next(request)

        # Check if this request used a PAT token
        # (set by get_current_token_from_pat dependency)
        pat_audit_info = getattr(request.state, "pat_audit_info", None)

        if pat_audit_info and pat_audit_info.get("token_id"):
            # Only log if we have a token ID (token was found)
            # Determine if request was authorized based on status code
            authorized = 200 <= response.status_code < 300

            # Determine reason for failure
            reason = None
            if not authorized:
                # Use specific failure reason if set (e.g., "Token revoked", "Token expired")
                reason = pat_audit_info.get("failure_reason")
                if not reason:
                    # Fallback to generic reasons based on status code
                    if response.status_code == 403:
                        reason = "Insufficient permissions"
                    elif response.status_code == 401:
                        reason = "Unauthorized"
                    elif response.status_code >= 500:
                        reason = "Internal server error"
                    else:
                        reason = f"HTTP {response.status_code}"

            # Log audit entry directly (ensure it's written before response)
            await self._log_audit(
                session=pat_audit_info["session"],
                token_id=pat_audit_info["token_id"],
                ip_address=pat_audit_info["ip_address"],
                method=pat_audit_info["method"],
                endpoint=pat_audit_info["endpoint"],
                status_code=response.status_code,
                authorized=authorized,
                reason=reason,
            )

        return response

    async def _log_audit(
        self,
        session,
        token_id,
        ip_address: str,
        method: str,
        endpoint: str,
        status_code: int,
        authorized: bool,
        reason: str | None = None,
    ):
        """Log audit entry using token usecase.

        This method is called asynchronously after the response is sent.
        It uses the same session from the request but in a new transaction.

        Args:
            session: Database session from request
            token_id: Token UUID
            ip_address: Client IP
            method: HTTP method
            endpoint: API endpoint
            status_code: HTTP status code
            authorized: Whether request was authorized
            reason: Optional failure reason
        """
        try:
            # Use the same session from the request
            token_usecase = TokenUsecase(session=session)
            await token_usecase.log_token_usage(
                token_id=token_id,
                ip_address=ip_address,
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                authorized=authorized,
                reason=reason,
            )
        except Exception as e:
            # Don't let audit logging errors affect anything
            # In production, log this error to application logs
            import logging
            logging.error(f"Failed to log audit entry: {e}")
