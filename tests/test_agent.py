import json
from pathlib import Path

import pytest

from app.agent.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    StructuredOutputError,
)
from app.agent.extractor import StructuredOutputAgent
from app.providers.mock_provider import MockProvider
from app.schemas.invoice import Invoice

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden_failures"


# 1. Valid JSON first attempt
@pytest.mark.asyncio
async def test_valid_json_first_attempt(sample_invoice_text, valid_invoice_json):
    provider = MockProvider(responses=[valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 1
    assert result.data.invoice_number == "INV-2024-8841"
    assert result.data.total == 2976.88
    assert len(provider.call_history) == 1


# 2. Malformed JSON with recovery after retry
@pytest.mark.asyncio
async def test_malformed_json_recovery(sample_invoice_text, valid_invoice_json):
    # Attempt 1: Truncated JSON without closing brace (03_unclosed_brace.txt)
    # Attempt 2: Valid JSON
    malformed = (GOLDEN_DIR / "03_unclosed_brace.txt").read_text()
    provider = MockProvider(responses=[malformed, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert result.data.invoice_number == "INV-2024-8841"
    assert len(provider.call_history) == 2
    # Verify corrective prompt was sent in attempt 2
    assert "JSON Parsing Error: Incomplete JSON output" in provider.call_history[1]["prompt"]


# 3. Valid JSON but schema-invalid (e.g. math mismatch)
@pytest.mark.asyncio
async def test_schema_invalid_math_mismatch_recovery(sample_invoice_text, valid_invoice_json):
    # Attempt 1: Math mismatch (07_math_mismatch_totals.json)
    # Attempt 2: Valid JSON
    math_mismatch = (GOLDEN_DIR / "07_math_mismatch_totals.json").read_text()
    provider = MockProvider(responses=[math_mismatch, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert result.data.invoice_number == "INV-2024-8841"
    assert "does not match" in provider.call_history[1]["prompt"]


# 4. Missing required field with recovery
@pytest.mark.asyncio
async def test_missing_required_field_recovery(sample_invoice_text, valid_invoice_json):
    # Attempt 1: Missing "total" field (05_missing_required_total.json)
    # Attempt 2: Valid JSON
    missing_field = (GOLDEN_DIR / "05_missing_required_total.json").read_text()
    provider = MockProvider(responses=[missing_field, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert result.data.invoice_number == "INV-2024-8841"
    assert "Field 'total': Field required" in provider.call_history[1]["prompt"]


# 5. Wrong type with recovery
@pytest.mark.asyncio
async def test_wrong_type_recovery(sample_invoice_text, valid_invoice_json):
    # Attempt 1: subtotal is string "five hundred dollars" (06_wrong_type_subtotal.json)
    # Attempt 2: Valid JSON
    wrong_type = (GOLDEN_DIR / "06_wrong_type_subtotal.json").read_text()
    provider = MockProvider(responses=[wrong_type, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert result.data.invoice_number == "INV-2024-8841"
    assert "subtotal" in provider.call_history[1]["prompt"]


# 6. Partially valid output with recovery
@pytest.mark.asyncio
async def test_partially_valid_output_recovery(sample_invoice_text, valid_invoice_json):
    # Missing customer.name and tax is negative
    partial = json.dumps(
        {
            "invoice_number": "INV-2024-PARTIAL",
            "supplier": {"name": "Tech Corp"},
            "customer": {},  # missing name
            "invoice_date": "2024-04-10",
            "currency": "USD",
            "line_items": [{"description": "Item 1", "quantity": 1.0, "unit_price": 100.0, "total": 100.0}],
            "subtotal": 100.0,
            "tax": -10.0,  # invalid negative
            "total": 90.0,
        }
    )
    provider = MockProvider(responses=[partial, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert "customer.name" in provider.call_history[1]["prompt"]


# 7. Recovery after retry (multi-step: attempt 1 malformed -> attempt 2 schema invalid -> attempt 3 valid)
@pytest.mark.asyncio
async def test_recovery_after_multi_step_retry(sample_invoice_text, valid_invoice_json):
    attempt_1_malformed = "Here is your JSON:\n{'invoice_number': 'INV-1', 'total': "
    attempt_2_schema_err = (GOLDEN_DIR / "07_math_mismatch_totals.json").read_text()
    attempt_3_valid = valid_invoice_json

    provider = MockProvider(responses=[attempt_1_malformed, attempt_2_schema_err, attempt_3_valid])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 3
    assert result.data.invoice_number == "INV-2024-8841"
    assert len(provider.call_history) == 3


# 8. Maximum retry failure (exhausts budget, raises StructuredOutputError)
@pytest.mark.asyncio
async def test_maximum_retry_failure(sample_invoice_text):
    bad_output = (GOLDEN_DIR / "07_math_mismatch_totals.json").read_text()
    provider = MockProvider(responses=[bad_output, bad_output, bad_output])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    with pytest.raises(StructuredOutputError) as exc_info:
        await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    err = exc_info.value
    assert err.attempts == 3
    assert len(err.history) == 3
    assert "Failed to extract valid structured output after 3 attempts" in str(err)


# 9. Provider timeout
@pytest.mark.asyncio
async def test_provider_timeout(sample_invoice_text):
    timeout_exc = ProviderTimeoutError("Request timed out after 30s", provider="mock")
    provider = MockProvider(responses=[timeout_exc])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert "Request timed out" in str(exc_info.value)


# 10. Provider error
@pytest.mark.asyncio
async def test_provider_error(sample_invoice_text):
    api_exc = ProviderError("Internal server error from provider", provider="mock", status_code=500)
    provider = MockProvider(responses=[api_exc])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    with pytest.raises(ProviderError) as exc_info:
        await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert "Internal server error" in str(exc_info.value)
    assert exc_info.value.status_code == 500


# 11. Empty response
@pytest.mark.asyncio
async def test_empty_response_recovery(sample_invoice_text, valid_invoice_json):
    provider = MockProvider(responses=["   ", valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert "Empty response received" in provider.call_history[1]["prompt"]


# 12. Unexpected output (JSON array instead of object)
@pytest.mark.asyncio
async def test_unexpected_output_array_recovery(sample_invoice_text, valid_invoice_json):
    array_output = '[{"invoice_number": "INV-1"}]'
    provider = MockProvider(responses=[array_output, valid_invoice_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(document_text=sample_invoice_text, model_cls=Invoice)

    assert result.attempts == 2
    assert "received a JSON array" in provider.call_history[1]["prompt"]
