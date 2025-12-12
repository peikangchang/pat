"""ID generation utilities."""
from uuid import UUID
from uuid6 import uuid7


def generate_uuid7() -> UUID:
    """Generate a UUIDv7 (time-sortable UUID)."""
    return uuid7()
