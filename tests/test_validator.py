import json
from pathlib import Path

import pytest

from app.agent.exceptions import SchemaValidationError
from app.agent.validator import SchemaValidator
from app.schemas.invoice import Invoice

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden_failures"


def test_validator_valid_invoice(valid_invoice_dict):
    result = SchemaValidator.validate(valid_invoice_dict, Invoice)
    assert isinstance(result, Invoice)
    assert result.invoice_number == "INV-2024-8841"
    assert result.total == 2976.88


def test_validator_missing_required_field_fixture():
    content = json.loads((GOLDEN_DIR / "05_missing_required_total.json").read_text())
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(content, Invoice)

    errs = exc_info.value.errors
    fields = [e["field"] for e in errs]
    assert "total" in fields
    assert any(e["category"] == "missing_field" for e in errs)


def test_validator_wrong_type_fixture():
    content = json.loads((GOLDEN_DIR / "06_wrong_type_subtotal.json").read_text())
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(content, Invoice)

    errs = exc_info.value.errors
    subtotal_err = next(e for e in errs if "subtotal" in e["field"])
    assert subtotal_err["category"] == "type_error"
    assert subtotal_err["received"] == "five hundred dollars"


def test_validator_math_mismatch_fixture():
    content = json.loads((GOLDEN_DIR / "07_math_mismatch_totals.json").read_text())
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(content, Invoice)

    errs = exc_info.value.errors
    assert any(e["category"] == "math_mismatch" for e in errs)
    assert any("does not match" in e["message"] for e in errs)


def test_validator_empty_line_items_fixture():
    content = json.loads((GOLDEN_DIR / "08_empty_line_items.json").read_text())
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(content, Invoice)

    errs = exc_info.value.errors
    assert any("line_items" in e["field"] for e in errs)


def test_validator_line_item_math_mismatch(valid_invoice_dict):
    # Alter line item 0 total to conflict with quantity * unit_price
    invalid_data = dict(valid_invoice_dict)
    invalid_data["line_items"] = [
        {
            "description": "GPU Cluster",
            "quantity": 2.0,
            "unit_price": 1000.0,
            "total": 9999.0,  # 2 * 1000 = 2000, not 9999
        }
    ]
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(invalid_data, Invoice)

    errs = exc_info.value.errors
    assert any("line_items.0.total" in e["field"] for e in errs)


def test_validator_due_date_before_invoice_date(valid_invoice_dict):
    invalid_data = dict(valid_invoice_dict)
    invalid_data["invoice_date"] = "2024-05-15"
    invalid_data["due_date"] = "2024-05-01"  # Due before invoice date

    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidator.validate(invalid_data, Invoice)

    errs = exc_info.value.errors
    assert any("Due date" in e["message"] for e in errs)
