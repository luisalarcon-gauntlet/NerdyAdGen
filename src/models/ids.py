"""UUID4 generation for model IDs. No imports from other src/ modules."""
import uuid


def generate_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())
