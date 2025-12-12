"""User usecase (stub implementation)."""
from app.domain.permissions import parse_scope, get_implied_permissions


class UserUsecase:
    """Stub usecase for user operations.

    This is a stub implementation that returns mock data.
    In a real application, this would interact with actual user repositories.
    """

    def _find_granted_by(self, user_scopes: list[str], required_scope: str) -> str | None:
        """Find which scope granted the required permission.

        Args:
            user_scopes: User's granted scopes
            required_scope: Required scope

        Returns:
            The scope that granted the permission, or None
        """
        try:
            required_resource, required_permission = parse_scope(required_scope)
        except ValueError:
            return None

        # Check each user scope
        for scope in user_scopes:
            try:
                resource, permission = parse_scope(scope)
            except ValueError:
                continue

            # Only check scopes for the same resource
            if resource != required_resource:
                continue

            # Get all permissions implied by this scope
            implied_permissions = get_implied_permissions(resource, permission)

            # Check if required permission is in the implied permissions
            if required_permission in implied_permissions:
                return scope

        return None

    async def get_current_user(self, user_id: str, scopes: list[str]) -> dict:
        """Get current user info (stub).

        Args:
            user_id: Current user ID
            scopes: User's granted scopes

        Returns:
            Mock current user info
        """
        required_scope = "users:read"
        granted_by = self._find_granted_by(scopes, required_scope)

        return {
            "endpoint": "/api/v1/users/me",
            "method": "GET",
            "required_scope": required_scope,
            "granted_by": granted_by,
            "your_scopes": scopes,
            "message": "This is a stub implementation",
            "user": {
                "id": user_id,
                "username": "current_user",
                "email": "user@example.com",
                "created_at": "2025-01-01T00:00:00Z",
            },
        }

    async def update_user(self, user_id: str, scopes: list[str]) -> dict:
        """Update user (stub).

        Args:
            user_id: User ID
            scopes: User's granted scopes

        Returns:
            Mock update result
        """
        required_scope = "users:write"
        granted_by = self._find_granted_by(scopes, required_scope)

        return {
            "endpoint": f"/api/v1/users/{user_id}",
            "method": "PUT",
            "required_scope": required_scope,
            "granted_by": granted_by,
            "your_scopes": scopes,
            "message": "This is a stub implementation",
            "updated": True,
        }
