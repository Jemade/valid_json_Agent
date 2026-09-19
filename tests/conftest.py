import json
from pathlib import Path

import pytest

from app.telemetry.metrics import metrics

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def reset_metrics():
    """Ensure clean metrics for every test."""
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def sample_invoice_text() -> str:
    path = FIXTURES_DIR / "invoice_valid.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def messy_invoice_text() -> str:
    path = FIXTURES_DIR / "invoice_messy.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def valid_invoice_dict() -> dict:
    return {
        "invoice_number": "INV-2024-8841",
        "supplier": {
            "name": "Apex Cloud Technologies Inc.",
            "tax_id": "US-99482104",
            "address": "100 Silicon Blvd, Suite 400, San Jose, CA 95134",
            "email": "billing@apexcloud.io",
        },
        "customer": {
            "name": "Northwind Dynamics LLC",
            "tax_id": "US-11029384",
            "address": "500 Enterprise Way, Austin, TX 78701",
            "email": "ap@northwind.com",
        },
        "invoice_date": "2024-04-10",
        "due_date": "2024-05-10",
        "currency": "USD",
        "line_items": [
            {
                "description": "Dedicated GPU Cluster (H100)",
                "quantity": 2.0,
                "unit_price": 1200.0,
                "total": 2400.0,
            },
            {
                "description": "High-Performance Storage (10TB)",
                "quantity": 1.0,
                "unit_price": 350.0,
                "total": 350.0,
            },
        ],
        "subtotal": 2750.0,
        "tax": 226.88,
        "total": 2976.88,
    }


@pytest.fixture
def valid_invoice_json(valid_invoice_dict) -> str:
    return json.dumps(valid_invoice_dict)
