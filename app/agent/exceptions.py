from typing import Any


class ExtractionError(Exception):
    """Base exception for extraction agent errors."""


class JSONParseError(ExtractionError):
    """Raised when the LLM output cannot be parsed as JSON."""

    def __init__(self, message: str, raw_snippet: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.message = message
        self.raw_snippet = raw_snippet
        self.line = line
        self.column = column


class SchemaValidationError(ExtractionError):
    """Raised when JSON output fails Pydantic schema validation."""

    def __init__(self, message: str, errors: list[dict[str, Any]], parsed_data: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors
        self.parsed_data = parsed_data


class StructuredOutputError(ExtractionError):
    """Raised when max retry budget is exhausted without a valid structured result."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Exception | None = None,
        history: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.attempts = attempts
        self.last_error = last_error
        self.history = history or []


class ProviderError(ExtractionError):
    """Raised when an upstream LLM provider fails (e.g. 5xx, rate limits)."""

    def __init__(self, message: str, provider: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class ProviderTimeoutError(ProviderError):
    """Raised when an upstream LLM provider times out."""

    def __init__(self, message: str, provider: str):
        super().__init__(message=message, provider=provider, status_code=408)
