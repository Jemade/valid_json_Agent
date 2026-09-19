import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from app.agent.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    StructuredOutputError,
)
from app.agent.extractor import StructuredOutputAgent
from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.mock_provider import MockProvider
from app.providers.openai_provider import OpenAIProvider
from app.schemas.api import (
    ErrorResponse,
    ExtractionRequest,
    ExtractionResponse,
    HealthResponse,
    MetricsResponse,
)
from app.schemas.invoice import Invoice
from app.telemetry.logging import configure_logging, get_logger
from app.telemetry.metrics import metrics

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(log_level=settings.log_level, environment=settings.environment)
    logger.info("Starting Structured Output Agent API", environment=settings.environment)
    yield
    logger.info("Shutting down Structured Output Agent API")


app = FastAPI(
    title="Structured Output Agent API",
    description="Production-grade API converting unstructured documents to validated Pydantic models with corrective retries.",
    version="0.1.0",
    lifespan=lifespan,
)


def get_provider(provider_name: str, model: str | None = None) -> LLMProvider:
    """Instantiate provider adapter based on requested name."""
    name = (provider_name or settings.default_provider).lower()

    if name == "mock":
        return MockProvider(model=model or "mock-model")
    elif name == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=model or settings.default_model,
            timeout=settings.request_timeout_seconds,
        )
    elif name == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            model=model or "claude-3-5-sonnet-20241022",
            timeout=settings.request_timeout_seconds,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: '{provider_name}'. Supported: 'mock', 'openai', 'anthropic'",
        )


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.get("/metrics", response_model=MetricsResponse, tags=["System"])
async def get_metrics() -> MetricsResponse:
    """Operational metrics endpoint."""
    return MetricsResponse(**metrics.get_metrics())


@app.post(
    "/v1/extract",
    response_model=ExtractionResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation failed after retries"},
        502: {"model": ErrorResponse, "description": "Upstream LLM provider failure"},
        504: {"model": ErrorResponse, "description": "Upstream LLM provider timeout"},
    },
    tags=["Extraction"],
)
async def extract_document(req: ExtractionRequest) -> ExtractionResponse | JSONResponse:
    """Extract structured, validated invoice data from raw text with automatic corrective retries."""
    request_id = str(uuid.uuid4())
    provider = get_provider(req.provider or settings.default_provider, req.model)

    agent = StructuredOutputAgent(
        provider=provider,
        max_retries=req.max_retries or settings.max_retries,
        log_raw_input=settings.log_raw_input,
        log_raw_output=settings.log_raw_output,
    )

    try:
        result = await agent.extract(
            document_text=req.document_text,
            model_cls=Invoice,
            request_id=request_id,
        )
        return ExtractionResponse(
            data=result.data,
            attempts=result.attempts,
            request_id=result.request_id,
            duration_ms=result.duration_ms,
        )

    except StructuredOutputError as exc:
        details: list[dict[str, Any]] = []
        if exc.last_error and hasattr(exc.last_error, "errors"):
            details = getattr(exc.last_error, "errors", [])

        error_body = ErrorResponse(
            error_type="StructuredOutputError",
            message=exc.message,
            attempts=exc.attempts,
            request_id=request_id,
            details=details,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_body.model_dump(),
        )

    except ProviderTimeoutError as exc:
        error_body = ErrorResponse(
            error_type="ProviderTimeoutError",
            message=exc.message,
            attempts=1,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=error_body.model_dump(),
        )

    except ProviderError as exc:
        error_body = ErrorResponse(
            error_type="ProviderError",
            message=exc.message,
            attempts=1,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=error_body.model_dump(),
        )
