# Interactive Demonstration Walkthrough

This guide walks through reproducing the core operational scenarios of the **Structured Output Agent**:
1. Clean extraction on the first attempt
2. Automated recovery from an invalid first response via corrective retry
3. Graceful failure and error reporting when the retry budget is exhausted
4. Inspecting structured logs and operational metrics

---

### Prerequisites

Ensure the virtual environment is activated and dependencies are installed:
```bash
source .venv/bin/activate
```

Start the FastAPI server in one terminal:
```bash
uvicorn app.main:app --port 8000
```

---

### Step 1: Send Valid Document (Success on First Attempt)

Send a clean invoice text to the extraction endpoint:

```bash
curl -X POST http://localhost:8000/v1/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "Invoice Number: INV-2024-8841\nDate: 2024-04-10\nSupplier: Apex Cloud Technologies Inc.\nCustomer: Northwind Dynamics LLC\nCurrency: USD\nLine items: Dedicated GPU Cluster (H100) 2.0 @ $1200.00 = $2400.00, Storage 1.0 @ $350.00 = $350.00\nSubtotal: $2750.00\nTax: $226.88\nTotal: $2976.88",
    "provider": "mock"
  }'
```

#### Expected Response:
```json
{
  "data": {
    "invoice_number": "INV-2024-8841",
    "supplier": {
      "name": "Apex Cloud Technologies Inc.",
      "tax_id": "US-99482104",
      "address": "100 Silicon Blvd, Suite 400, San Jose, CA 95134",
      "email": "billing@apexcloud.io"
    },
    "customer": {
      "name": "Northwind Dynamics LLC",
      "tax_id": "US-11029384",
      "address": "500 Enterprise Way, Austin, TX 78701",
      "email": "ap@northwind.com"
    },
    "invoice_date": "2024-04-10",
    "due_date": "2024-05-10",
    "currency": "USD",
    "line_items": [
      {
        "description": "Dedicated GPU Cluster (H100)",
        "quantity": 2.0,
        "unit_price": 1200.0,
        "total": 2400.0
      },
      {
        "description": "High-Performance Storage (10TB)",
        "quantity": 1.0,
        "unit_price": 350.0,
        "total": 350.0
      }
    ],
    "subtotal": 2750.0,
    "tax": 226.88,
    "total": 2976.88
  },
  "attempts": 1,
  "request_id": "188a87b5-0e31-419b-a019-3fbc7d9c661b",
  "duration_ms": 1.2
}
```

---

### Step 2: Automated Recovery via Corrective Retry

To demonstrate how the agent intercepts an invalid response, analyzes the validation failure, builds a targeted corrective prompt, and recovers on the next attempt, run this self-contained Python script:

```bash
python -c "
import asyncio
from app.agent.extractor import StructuredOutputAgent
from app.providers.mock_provider import MockProvider
from app.schemas.invoice import Invoice

async def demo_retry():
    # Attempt 1: Model outputs malformed JSON with math mismatch
    bad_attempt_1 = '''{
      \"invoice_number\": \"INV-RETRY-01\",
      \"supplier\": {\"name\": \"Alpha Inc\"},
      \"customer\": {\"name\": \"Omega Ltd\"},
      \"invoice_date\": \"2024-04-15\",
      \"currency\": \"USD\",
      \"line_items\": [{\"description\": \"Consulting\", \"quantity\": 1.0, \"unit_price\": 100.0, \"total\": 100.0}],
      \"subtotal\": 100.0,
      \"tax\": 10.0,
      \"total\": 999.0
    }'''

    # Attempt 2: Model corrects the total to 110.0
    good_attempt_2 = '''{
      \"invoice_number\": \"INV-RETRY-01\",
      \"supplier\": {\"name\": \"Alpha Inc\"},
      \"customer\": {\"name\": \"Omega Ltd\"},
      \"invoice_date\": \"2024-04-15\",
      \"currency\": \"USD\",
      \"line_items\": [{\"description\": \"Consulting\", \"quantity\": 1.0, \"unit_price\": 100.0, \"total\": 100.0}],
      \"subtotal\": 100.0,
      \"tax\": 10.0,
      \"total\": 110.0
    }'''

    provider = MockProvider(responses=[bad_attempt_1, good_attempt_2])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    result = await agent.extract(\"Sample Invoice Text\", model_cls=Invoice)
    print(f'Extraction Status: SUCCESS')
    print(f'Total Attempts: {result.attempts}')
    print(f'Corrected Total: {result.data.total}')
    print('\nCorrective Prompt Sent in Attempt 2:')
    print(provider.call_history[1]['prompt'])

asyncio.run(demo_retry())
"
```

#### Output:
```text
Extraction Status: SUCCESS
Total Attempts: 2
Corrected Total: 110.0

Corrective Prompt Sent in Attempt 2:
Your previous response in attempt 1 was invalid and rejected by the validator.

Schema Validation Errors:
- Field 'root': Value error, Total (999.00) does not match subtotal (100.00) + tax (10.00) = 110.00

Correct the issues identified above. Ensure all required fields are present, types are correct, and all mathematical constraints hold.
```

---

### Step 3: Exhausted Retry Budget (Graceful Failure)

When a model persistently produces invalid data across all attempts, the system prevents infinite loops and raises `StructuredOutputError`.

Run:
```bash
python -c "
import asyncio
from app.agent.exceptions import StructuredOutputError
from app.agent.extractor import StructuredOutputAgent
from app.providers.mock_provider import MockProvider
from app.schemas.invoice import Invoice

async def demo_exhaustion():
    broken_json = '{\"invoice_number\": \"INV-FAIL\", \"total\": \"not_a_number\"}'
    # Feed 3 consecutive invalid responses
    provider = MockProvider(responses=[broken_json, broken_json, broken_json])
    agent = StructuredOutputAgent(provider=provider, max_retries=3)

    try:
        await agent.extract(\"Sample Invoice\", model_cls=Invoice)
    except StructuredOutputError as exc:
        print(f'Caught expected exception: {type(exc).__name__}')
        print(f'Message: {exc.message}')
        print(f'Attempts exhausted: {exc.attempts}')
        print(f'Attempt history records: {len(exc.history)}')

asyncio.run(demo_exhaustion())
"
```

#### Output:
```text
Caught expected exception: StructuredOutputError
Message: Failed to extract valid structured output after 3 attempts
Attempts exhausted: 3
Attempt history records: 3
```

---

### Step 4: Inspecting Operational Metrics

Query the `/metrics` endpoint to view aggregated telemetry:

```bash
curl http://localhost:8000/metrics
```

#### Sample Metrics Output:
```json
{
  "total_requests": 2,
  "successful_validations": 1,
  "failed_validations": 1,
  "average_retries": 2.0,
  "retry_distribution": {
    "1": 1,
    "3": 1
  },
  "final_failure_rate": 0.5,
  "validation_failure_categories": {
    "type_error": 3,
    "missing_field": 6
  }
}
```
