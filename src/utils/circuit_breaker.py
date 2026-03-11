"""Per-service circuit breaker. One instance per external service."""
import time
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when the circuit is OPEN and the request is rejected."""

    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(f"Circuit open for service: {service}")


SERVICES = ["gemini", "claude", "database", "langsmith", "nano_banana"]

CIRCUIT_CONFIG = {
    "failure_threshold": 5,
    "cooldown_seconds": 60,
    "success_to_close": 1,
}


class CircuitBreaker:
    """One instance per service. Uses time.monotonic() for cooldown."""

    def __init__(self, service: str) -> None:
        self.service = service
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._threshold = CIRCUIT_CONFIG["failure_threshold"]
        self._cooldown = CIRCUIT_CONFIG["cooldown_seconds"]

    @property
    def state(self) -> CircuitState:
        return self._state

    def record_failure(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._consecutive_failures = 1
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def record_success(self) -> None:
        self._consecutive_failures = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._opened_at = None

    def check_can_attempt(self) -> None:
        """Raise CircuitOpenError if circuit is OPEN and cooldown has not elapsed."""
        if self._state == CircuitState.CLOSED:
            return
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._opened_at or 0)
            if elapsed >= self._cooldown:
                self._state = CircuitState.HALF_OPEN
                return
            raise CircuitOpenError(self.service)
        if self._state == CircuitState.HALF_OPEN:
            return
