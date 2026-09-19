import time
import uuid
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.agent.exceptions import (
    JSONParseError,
    SchemaValidationError,
)
from app.agent.parser import RobustJSONParser
from app.agent.prompt_builder import PromptBuilder
from app.agent.retry import RetryController
from app.agent.validator import SchemaValidator
from app.providers.base import LLMProvider
from app.schemas.invoice import Invoice
from app.telemetry.logging import get_logger
from app.telemetry.metrics import metrics

T = TypeVar("T", bound=BaseModel)
logger = get_logger("structured_output_agent")


@dataclass
class ExtractionResult(Generic[T]):
    data: T
    attempts: int
    request_id: str
    duration_ms: float
    raw_output: str | None = None


class StructuredOutputAgent:
    """Production-grade agent that extracts structured, validated Pydantic models from LLM responses

    with targeted corrective retries.
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_retries: int = 3,
        prompt_builder: PromptBuilder | None = None,
        parser: RobustJSONParser | None = None,
        validator: SchemaValidator | None = None,
        log_raw_input: bool = False,
        log_raw_output: bool = False,
    ):
        self.provider = provider
        self.max_retries = max_retries
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or RobustJSONParser()
        self.validator = validator or SchemaValidator()
        self.log_raw_input = log_raw_input
        self.log_raw_output = log_raw_output

    async def extract(
        self,
        document_text: str,
        model_cls: type[T] = Invoice,  # type: ignore[assignment]
        request_id: str | None = None,
    ) -> ExtractionResult[T]:
        """Execute extraction and validation loop with targeted corrective retries.

        Raises:
            StructuredOutputError: If retry budget is exhausted without valid output.
            ProviderError: If upstream LLM communication fails unrecoverably.
        """
        req_id = request_id or str(uuid.uuid4())
        start_time = time.perf_counter()
        controller = RetryController(max_attempts=self.max_retries)

        logger.info(
            "Starting extraction",
            request_id=req_id,
            max_retries=self.max_retries,
            target_schema=model_cls.__name__,
            document_length=len(document_text),
            **({"raw_document": document_text} if self.log_raw_input else {}),
        )

        last_raw_output = ""
        last_error: Exception | None = None

        while controller.can_retry():
            attempt = controller.next_attempt()

            if attempt == 1:
                prompt = self.prompt_builder.build_initial_prompt(document_text)
            else:
                assert last_error is not None
                prompt = self.prompt_builder.build_corrective_prompt(
                    document_text=document_text,
                    previous_output=last_raw_output,
                    error=last_error,
                    attempt=attempt - 1,
                )

            # Call provider
            try:
                response = await self.provider.complete(
                    prompt=prompt,
                    system_prompt=self.prompt_builder.SYSTEM_PROMPT,
                )
                last_raw_output = response.content
            except Exception as exc:
                # Provider errors (e.g. timeout, network) fail immediately
                total_duration = (time.perf_counter() - start_time) * 1000.0
                metrics.record_request(attempts=attempt, success=False)
                logger.error(
                    "Provider communication failed",
                    request_id=req_id,
                    attempt=attempt,
                    error=str(exc),
                    latency_ms=total_duration,
                )
                raise

            # Step 1: Parse JSON
            try:
                parsed_json = self.parser.parse(last_raw_output)
            except JSONParseError as parse_err:
                last_error = parse_err
                metrics.record_attempt_failure("json_syntax")
                controller.record_attempt(
                    attempt=attempt,
                    raw_output=last_raw_output,
                    error=parse_err,
                    latency_ms=response.latency_ms,
                    log_raw=self.log_raw_output,
                )
                logger.warning(
                    "JSON parsing failed",
                    request_id=req_id,
                    attempt=attempt,
                    error_type="JSONParseError",
                    message=parse_err.message,
                    snippet=parse_err.raw_snippet[:150],
                    latency_ms=response.latency_ms,
                )

                if not controller.can_retry():
                    total_duration = (time.perf_counter() - start_time) * 1000.0
                    metrics.record_request(attempts=attempt, success=False)
                    controller.raise_exhausted(last_error=parse_err)
                continue

            # Step 2: Validate Pydantic Schema
            try:
                validated_model = self.validator.validate(parsed_json, model_cls)
            except SchemaValidationError as val_err:
                last_error = val_err
                for err_item in val_err.errors:
                    metrics.record_attempt_failure(err_item["category"])

                controller.record_attempt(
                    attempt=attempt,
                    raw_output=last_raw_output,
                    error=val_err,
                    latency_ms=response.latency_ms,
                    log_raw=self.log_raw_output,
                )
                logger.warning(
                    "Schema validation failed",
                    request_id=req_id,
                    attempt=attempt,
                    error_type="SchemaValidationError",
                    errors_count=len(val_err.errors),
                    errors=val_err.errors,
                    latency_ms=response.latency_ms,
                )

                if not controller.can_retry():
                    total_duration = (time.perf_counter() - start_time) * 1000.0
                    metrics.record_request(attempts=attempt, success=False)
                    controller.raise_exhausted(last_error=val_err)
                continue

            # Success!
            total_duration = (time.perf_counter() - start_time) * 1000.0
            metrics.record_request(attempts=attempt, success=True)
            logger.info(
                "Extraction succeeded",
                request_id=req_id,
                attempts=attempt,
                duration_ms=round(total_duration, 2),
            )

            return ExtractionResult(
                data=validated_model,
                attempts=attempt,
                request_id=req_id,
                duration_ms=round(total_duration, 2),
                raw_output=last_raw_output if self.log_raw_output else None,
            )

        # Fallback if loop finishes without returning (should not occur)
        total_duration = (time.perf_counter() - start_time) * 1000.0
        metrics.record_request(attempts=controller.current_attempt, success=False)
        controller.raise_exhausted(last_error=last_error)
        raise RuntimeError("Unreachable")
