"""Exponential backoff retry decorator for async functions."""
import asyncio
import random
from functools import wraps
from typing import Callable, Tuple, TypeVar

from src.utils.logger import structured_logger

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exception_types: Tuple[type, ...] = (Exception,),
    service: str = "api",
) -> Callable:
    """Decorate an async function to retry on specified exceptions with exponential backoff + jitter."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exception_types as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise
                    delay = min(
                        base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1.0),
                        max_delay,
                    )
                    structured_logger.log(
                        "retry_attempt",
                        service=service,
                        attempt_number=attempt,
                        delay_seconds=round(delay, 2),
                    )
                    await asyncio.sleep(delay)
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator
