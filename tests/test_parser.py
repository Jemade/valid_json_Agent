from pathlib import Path

import pytest

from app.agent.exceptions import JSONParseError
from app.agent.parser import RobustJSONParser

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden_failures"


@pytest.fixture
def parser() -> RobustJSONParser:
    return RobustJSONParser()


def test_parse_valid_clean_json(parser: RobustJSONParser):
    raw = '{"name": "Invoice 1", "amount": 100.5}'
    result = parser.parse(raw)
    assert result == {"name": "Invoice 1", "amount": 100.5}


def test_parse_markdown_wrapped_fixture(parser: RobustJSONParser):
    content = (GOLDEN_DIR / "01_markdown_wrapped.txt").read_text()
    result = parser.parse(content)
    assert result["invoice_number"] == "INV-2024-001"
    assert result["total"] == 110.0


def test_parse_conversational_prefix_fixture(parser: RobustJSONParser):
    content = (GOLDEN_DIR / "02_conversational_prefix.txt").read_text()
    result = parser.parse(content)
    assert result["invoice_number"] == "INV-2024-002"
    assert result["total"] == 1440.0


def test_parse_unclosed_brace_fixture(parser: RobustJSONParser):
    content = (GOLDEN_DIR / "03_unclosed_brace.txt").read_text()
    with pytest.raises(JSONParseError) as exc_info:
        parser.parse(content)
    assert "Incomplete JSON output" in str(exc_info.value)


def test_parse_single_quotes_fixture(parser: RobustJSONParser):
    content = (GOLDEN_DIR / "04_single_quotes.txt").read_text()
    result = parser.parse(content)
    assert result["invoice_number"] == "INV-2024-004"
    assert result["total"] == 960.0


def test_parse_trailing_comma_repair(parser: RobustJSONParser):
    raw = '{"items": ["apple", "banana", ], "total": 50.0, }'
    result = parser.parse(raw)
    assert result == {"items": ["apple", "banana"], "total": 50.0}


def test_parse_empty_string(parser: RobustJSONParser):
    with pytest.raises(JSONParseError) as exc_info:
        parser.parse("   \n  ")
    assert "Empty response received" in str(exc_info.value)


def test_parse_no_json_object_found(parser: RobustJSONParser):
    with pytest.raises(JSONParseError) as exc_info:
        parser.parse("I am an AI assistant and I cannot find an invoice here.")
    assert "No JSON object detected" in str(exc_info.value)


def test_parse_json_array_rejected(parser: RobustJSONParser):
    with pytest.raises(JSONParseError) as exc_info:
        parser.parse('[{"item": "desk"}, {"item": "chair"}]')
    assert "received a JSON array" in str(exc_info.value)


def test_parse_malformed_syntax_error(parser: RobustJSONParser):
    with pytest.raises(JSONParseError) as exc_info:
        parser.parse('{"invoice_number": "INV-1", "total": }')
    assert "Invalid JSON syntax" in str(exc_info.value)
    assert exc_info.value.line is not None
