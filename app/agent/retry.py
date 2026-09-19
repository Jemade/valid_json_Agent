from typing import Any

from app.agent.exceptions import StructuredOutputError


class RetryController:
    """Manages attempt counts, retry budget, and execution history for structured output extraction."""

    def __init__(self, max_attempts: int = 3):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.max_attempts = max_attempts
        self.current_attempt: int = 0
        self.history: list[dict[str, Any]] = []

    def can_retry(self) -> bool:
        """Returns True if remaining attempts exist within the retry budget."""
        return self.current_attempt < self.max_attempts

    def next_attempt(self) -> int:
        """Advance and return the current attempt number."""
        self.current_attempt += 1
        return self.current_attempt

    def record_attempt(
        self,
        attempt: int,
        raw_output: str,
        error: Exception | None,
        latency_ms: float,
        log_raw: bool = False,
    ) -> None:
        """Record attempt diagnostic data into history."""
        record: dict[str, Any] = {
            "attempt": attempt,
            "latency_ms": latency_ms,
            "error_type": type(error).__name__ if error else None,
            "error_message": str(error) if error else None,
        }
        if log_raw:
            record["raw_output"] = raw_output

        self.history.append(record)

    def raise_exhausted(self, last_error: Exception | None = None) -> None:
        """Raise StructuredOutputError when retry budget is exhausted."""
        raise StructuredOutputError(
            message=f"Failed to extract valid structured output after {self.max_attempts} attempts",
            attempts=self.current_attempt,
            last_error=last_error,
            history=self.history,
        )
