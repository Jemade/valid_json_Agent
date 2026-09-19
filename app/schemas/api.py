from typing import Any

from pydantic import BaseModel, Field

from app.schemas.invoice import Invoice


class ExtractionRequest(BaseModel):
    document_text: str = Field(..., min_length=1, description="Raw text of the document to extract")
    provider: str | None = Field(default=None, description="LLM provider: 'mock', 'openai', or 'anthropic'")
    model: str | None = Field(default=None, description="Specific model to use")
    max_retries: int | None = Field(default=None, ge=1, le=10, description="Max retry attempts")


class ExtractionResponse(BaseModel):
    data: Invoice = Field(..., description="Validated structured invoice")
    attempts: int = Field(..., ge=1, description="Number of attempts taken")
    request_id: str = Field(..., description="Unique request identifier")
    duration_ms: float = Field(..., ge=0, description="Total extraction latency in milliseconds")


class ErrorResponse(BaseModel):
    error_type: str = Field(..., description="Machine-readable error type")
    message: str = Field(..., description="Human-readable error description")
    attempts: int = Field(..., ge=1, description="Number of attempts made before failing")
    request_id: str = Field(..., description="Unique request identifier")
    details: list[dict[str, Any]] | None = Field(default=None, description="Structured validation error items")


class MetricsResponse(BaseModel):
    total_requests: int
    successful_validations: int
    failed_validations: int
    average_retries: float
    retry_distribution: dict[str, int]
    final_failure_rate: float
    validation_failure_categories: dict[str, int]


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
