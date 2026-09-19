import threading
from typing import Any


class MetricsCollector:
    """Thread-safe collector for extraction and validation metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._successful_validations: int = 0
        self._failed_validations: int = 0
        self._total_attempts: int = 0
        self._retry_distribution: dict[int, int] = {}
        self._failure_categories: dict[str, int] = {}

    def record_attempt_failure(self, category: str) -> None:
        """Record a single attempt failure category."""
        with self._lock:
            self._failure_categories[category] = self._failure_categories.get(category, 0) + 1

    def record_request(self, attempts: int, success: bool) -> None:
        """Record the final outcome of an extraction request."""
        with self._lock:
            self._total_requests += 1
            self._total_attempts += attempts

            if success:
                self._successful_validations += 1
            else:
                self._failed_validations += 1

            self._retry_distribution[attempts] = self._retry_distribution.get(attempts, 0) + 1

    def get_metrics(self) -> dict[str, Any]:
        """Compute and return the structured metrics snapshot."""
        with self._lock:
            avg_retries = round(self._total_attempts / self._total_requests, 2) if self._total_requests > 0 else 0.0
            failure_rate = (
                round(self._failed_validations / self._total_requests, 4) if self._total_requests > 0 else 0.0
            )

            # String keys for JSON serialization
            distribution_str_keys = {str(k): v for k, v in sorted(self._retry_distribution.items())}

            return {
                "total_requests": self._total_requests,
                "successful_validations": self._successful_validations,
                "failed_validations": self._failed_validations,
                "average_retries": avg_retries,
                "retry_distribution": distribution_str_keys,
                "final_failure_rate": failure_rate,
                "validation_failure_categories": dict(self._failure_categories),
            }

    def reset(self) -> None:
        """Reset all metric counters (primarily for test isolation)."""
        with self._lock:
            self._total_requests = 0
            self._successful_validations = 0
            self._failed_validations = 0
            self._total_attempts = 0
            self._retry_distribution.clear()
            self._failure_categories.clear()


# Global shared collector
metrics = MetricsCollector()
