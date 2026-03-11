"""UUID4 generation. No imports from other src/ except stdlib."""
import uuid


def generate_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())
