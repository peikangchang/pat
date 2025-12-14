"""Permission system with hierarchical scopes."""
from enum import Enum
from typing import Any


class ResourceType(str, Enum):
    """Resource types."""
    WORKSPACESS = "workspacess"
    USERS = "users"
    FCS = "fcs"


class WorkspacesPermission(str, Enum):
    """Workspaces permissions (hierarchical: admin > delete > write > read)."""
    ADMIN = "admin"
    DELETE = "delete"
    WRITE = "write"
    READ = "read"


class UsersPermission(str, Enum):
    """Users permissions (hierarchical: write > read)."""
    WRITE = "write"
    READ = "read"


class FCSPermission(str, Enum):
    """FCS permissions (hierarchical: analyze > write > read)."""
    ANALYZE = "analyze"
    WRITE = "write"
    READ = "read"


# Permission hierarchy definitions (higher level includes all lower levels)
PERMISSION_HIERARCHY: dict[str, dict[str, list[str]]] = {
    ResourceType.WORKSPACESS: {
        WorkspacesPermission.ADMIN: [
            WorkspacesPermission.DELETE,
            WorkspacesPermission.WRITE,
            WorkspacesPermission.READ,
        ],
        WorkspacesPermission.DELETE: [
            WorkspacesPermission.WRITE,
            WorkspacesPermission.READ,
        ],
        WorkspacesPermission.WRITE: [
            WorkspacesPermission.READ,
        ],
        WorkspacesPermission.READ: [],
    },
    ResourceType.USERS: {
        UsersPermission.WRITE: [UsersPermission.READ],
        UsersPermission.READ: [],
    },
    ResourceType.FCS: {
        FCSPermission.ANALYZE: [FCSPermission.WRITE, FCSPermission.READ],
        FCSPermission.WRITE: [FCSPermission.READ],
        FCSPermission.READ: [],
    },
}


def format_scope(resource: str, permission: str) -> str:
    """Format a scope string (e.g., 'workspacess:read')."""
    return f"{resource}:{permission}"


def parse_scope(scope: str) -> tuple[str, str]:
    """Parse a scope string into resource and permission.

    Args:
        scope: Scope string (e.g., 'workspacess:read')

    Returns:
        Tuple of (resource, permission)

    Raises:
        ValueError: If scope format is invalid
    """
    parts = scope.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid scope format: {scope}")
    return parts[0], parts[1]


def get_implied_permissions(resource: str, permission: str) -> list[str]:
    """Get all permissions implied by the given permission (including itself).

    Args:
        resource: Resource type (e.g., 'workspacess')
        permission: Permission level (e.g., 'admin')

    Returns:
        List of all implied permissions including the given one

    Example:
        >>> get_implied_permissions('workspacess', 'admin')
        ['admin', 'delete', 'write', 'read']
    """
    if resource not in PERMISSION_HIERARCHY:
        return [permission]

    resource_hierarchy = PERMISSION_HIERARCHY[resource]
    if permission not in resource_hierarchy:
        return [permission]

    # Return the permission itself plus all its implied permissions
    return [permission] + resource_hierarchy[permission]


def has_permission(user_scopes: list[str], required_scope: str) -> bool:
    """Check if user has the required permission.

    Args:
        user_scopes: List of scopes the user has (e.g., ['workspacess:admin', 'fcs:read'])
        required_scope: The required scope (e.g., 'workspacess:write')

    Returns:
        True if user has the required permission (directly or through hierarchy)

    Example:
        >>> has_permission(['workspacess:admin'], 'workspacess:read')
        True
        >>> has_permission(['workspacess:read'], 'workspacess:write')
        False
    """
    try:
        required_resource, required_permission = parse_scope(required_scope)
    except ValueError:
        return False

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
            return True

    return False


def validate_scope(scope: str) -> bool:
    """Validate if a scope string is valid.

    Args:
        scope: Scope string to validate

    Returns:
        True if scope is valid, False otherwise
    """
    try:
        resource, permission = parse_scope(scope)
    except ValueError:
        return False

    # Check if resource exists
    if resource not in PERMISSION_HIERARCHY:
        return False

    # Check if permission exists for this resource
    if permission not in PERMISSION_HIERARCHY[resource]:
        return False

    return True


def validate_scopes(scopes: list[str]) -> tuple[bool, list[str]]:
    """Validate a list of scopes.

    Args:
        scopes: List of scope strings to validate

    Returns:
        Tuple of (all_valid, invalid_scopes)
    """
    invalid_scopes = [scope for scope in scopes if not validate_scope(scope)]
    return len(invalid_scopes) == 0, invalid_scopes
