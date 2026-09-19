from app.agent.exceptions import JSONParseError, SchemaValidationError
from app.agent.prompt_builder import PromptBuilder


def test_initial_prompt_contains_document_and_schema():
    builder = PromptBuilder()
    doc = "Invoice Number: INV-999\nTotal: 100 USD"
    prompt = builder.build_initial_prompt(doc)

    assert "INV-999" in prompt
    assert "Schema Specification:" in prompt
    assert "Output ONLY the JSON object" in prompt


def test_corrective_prompt_for_json_parse_error():
    builder = PromptBuilder()
    doc = "Invoice Number: INV-999"
    err = JSONParseError("Incomplete JSON output", raw_snippet='{"invoice_number": "INV-999"')
    prompt = builder.build_corrective_prompt(
        document_text=doc,
        previous_output='{"invoice_number": "INV-999"',
        error=err,
        attempt=1,
    )

    assert "previous response in attempt 1 was invalid" in prompt
    assert "JSON Parsing Error: Incomplete JSON output" in prompt
    assert '{"invoice_number": "INV-999"' in prompt
    assert "Return ONLY the corrected JSON object" in prompt


def test_corrective_prompt_for_schema_validation_error():
    builder = PromptBuilder()
    doc = "Invoice Number: INV-999"
    err = SchemaValidationError(
        message="Validation failed",
        errors=[
            {
                "field": "total",
                "category": "math_mismatch",
                "message": "Total (150.00) does not match subtotal (100.00) + tax (20.00) = 120.00",
                "received": 150.0,
            },
            {
                "field": "customer.name",
                "category": "missing_field",
                "message": "Field required",
                "received": None,
            },
        ],
    )
    prompt = builder.build_corrective_prompt(
        document_text=doc,
        previous_output='{"total": 150.0}',
        error=err,
        attempt=2,
    )

    assert "previous response in attempt 2 was invalid" in prompt
    assert (
        "- Field 'total': Total (150.00) does not match subtotal (100.00) + tax (20.00) = 120.00 (received: 150.0)"
        in prompt
    )
    assert "- Field 'customer.name': Field required" in prompt
