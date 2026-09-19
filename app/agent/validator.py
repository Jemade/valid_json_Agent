from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.agent.exceptions import SchemaValidationError

T = TypeVar("T", bound=BaseModel)


class SchemaValidator:
    """Validates parsed JSON against a target Pydantic schema and extracts

    granular diagnostics on failure.
    """

    @staticmethod
    def validate(data: dict[str, Any], model_cls: type[T]) -> T:
        """Validate parsed dictionary against the Pydantic model.

        Raises:
            SchemaValidationError: If validation fails.
        """
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            extracted_errors = SchemaValidator._extract_errors(exc)
            raise SchemaValidationError(
                message=f"Schema validation failed with {len(extracted_errors)} errors",
                errors=extracted_errors,
                parsed_data=data,
            ) from exc

    @staticmethod
    def _extract_errors(exc: ValidationError) -> list[dict[str, Any]]:
        extracted = []
        for err in exc.errors():
            field_path = ".".join(str(part) for part in err.get("loc", []))
            err_type = err.get("type", "unknown")
            msg = err.get("msg", "")
            raw_input = err.get("input")

            # Categorize error for telemetry and prompt targeting
            category = SchemaValidator._categorize_error(err_type, msg)

            # Sanitize received value for reporting
            safe_received = SchemaValidator._sanitize_received(raw_input)

            extracted.append(
                {
                    "field": field_path or "root",
                    "category": category,
                    "error_type": err_type,
                    "message": msg,
                    "received": safe_received,
                }
            )
        return extracted

    @staticmethod
    def _categorize_error(err_type: str, msg: str) -> str:
        if "missing" in err_type:
            return "missing_field"
        if "type" in err_type or "parsing" in err_type or "int" in err_type or "float" in err_type:
            return "type_error"
        if "does not match" in msg.lower() or "sum" in msg.lower():
            return "math_mismatch"
        if "greater" in msg.lower() or "earlier" in msg.lower() or "length" in msg.lower():
            return "constraint_violation"
        return "schema_violation"

    @staticmethod
    def _sanitize_received(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, (int, float, bool)):
            return val
        if isinstance(val, str):
            return val[:100] + ("..." if len(val) > 100 else "")
        if isinstance(val, (list, dict)):
            return f"<{type(val).__name__} with {len(val)} items>"
        return str(val)[:100]
