# Engineering Design Decisions

This document details the architectural and design decisions behind the **Structured Output Agent**. These decisions reflect real-world constraints in production AI systems where downstream software requires deterministic, type-safe data from inherently probabilistic Large Language Models.

---

### 1. Why Pydantic v2?

Downstream systems (databases, accounting software, ERPs, payment gateways) cannot consume arbitrary nested dictionaries without runtime risk. Pydantic v2 was chosen because:

- **Strict Schema Definition**: It provides compiled Rust-backed validation (`pydantic-core`), eliminating the runtime overhead of pure Python schema validators.
- **Granular Error Metadata**: Pydantic's `ValidationError.errors()` exposes exact field paths (`loc`), machine-readable error types (`type`), input values, and descriptive messages. This metadata is essential for feeding targeted error diagnostics back into corrective LLM prompts.
- **Cross-Field and Arithmetic Invariants**: Validating invoices requires verifying relationships across fields (e.g. `subtotal + tax == total`, `sum(line_items.total) == subtotal`, `due_date >= invoice_date`). Pydantic's `@model_validator(mode="after")` and `@field_validator` cleanly encapsulate business logic directly alongside data types.

---

### 2. Why Custom Validation & Error Reporting Instead of a Heavy Framework?

While libraries like `Instructor` provide wrappers around model endpoints, implementing our own validation, parsing, and retry layers provides several distinct production advantages:

- **Visibility & Control**: We have complete visibility into the exact prompt sent on each attempt, how raw strings are transformed, and how retries are scheduled.
- **Targeted Feedback Loops**: Generic frameworks often re-prompt with full schema dumps or naive error messages. Our `PromptBuilder` formats concise, human-readable error summaries (e.g. stating the exact math mismatch or missing field), minimizing prompt token bloat while guiding the LLM directly to the fix.
- **Zero Lock-in**: The system is decoupled from specific SDK features, allowing us to support any LLM provider via a lightweight `httpx` protocol without waiting for library updates.

---

### 3. Why Capped Retries with a Strict Retry Budget?

Unbounded retry loops are an anti-pattern in production systems for three reasons:

1. **Financial Cost**: Each retry consumes prompt and completion tokens. An infinite or high-limit loop on a stubborn syntax error or hallucinations can rapidly drain API budgets.
2. **Latency Bounds**: Real-time APIs and user-facing workflows have strict SLAs (e.g., 5–10 seconds). Three attempts balance recovery probability against total latency.
3. **Diminishing Returns**: Empirical observation of LLM behavior demonstrates that if a model cannot correct its output within 2–3 targeted feedback rounds, additional retries almost never succeed and frequently trigger hallucination loops.

When the budget is exhausted, the system halts immediately and raises a typed `StructuredOutputError` with the complete attempt history, enabling downstream fallback queues or human-in-the-loop review.

---

### 4. Why Provider Abstraction?

In enterprise environments, LLM vendor diversification is critical for reliability, pricing, and compliance:

- **No Vendor Lock-in**: Switching from OpenAI to Anthropic or a locally hosted vLLM/Ollama model should be a configuration change, not a code rewrite.
- **Offline Deterministic Testing**: By decoupling the agent from network SDKs through the `LLMProvider` protocol, the entire test suite runs deterministically in sub-second time using `MockProvider` without incurring network latency or API fees.
- **Resilience**: If a provider experiences an outage or rate limit degradation, the application layer can route traffic to an alternate provider using the same schema and retry controller.

---

### 5. Why Not Blindly Trust "JSON Mode" / Structured Outputs?

Major LLM providers offer "JSON mode" or "Structured Outputs" (e.g. OpenAI's `response_format: {"type": "json_object"}` or JSON Schema mode). While helpful, relying on them as the sole validation mechanism is insufficient for production:

1. **Syntax vs. Semantic Validity**: JSON mode guarantees only that the output is syntactically valid JSON. It does **not** guarantee:
   - That required fields are present or non-null.
   - That numeric values satisfy business ranges (`quantity > 0`).
   - That mathematical invariants hold (`subtotal + tax == total`).
   - That dates are valid calendar dates in chronological order.
2. **Provider Variability**: Anthropic, open-source models, and self-hosted instances have varying degrees of native JSON enforcement. A robust architecture must enforce schema guarantees at the application layer regardless of provider quirks.
3. **Silent Omissions**: Models in JSON mode frequently output valid JSON that silently omits fields or substitutes placeholder strings (e.g. `"N/A"` or `"unknown"`) when uncertain. Our Pydantic models forbid unexpected fields and validate value constraints strictly.

---

### 6. What Happens if Validation Never Succeeds?

When all configured attempts (default: 3) fail:

1. **Failure Telemetry**: The final failure is recorded in `MetricsCollector` (`failed_validations`, `final_failure_rate`, and the specific failure categories like `missing_field` or `math_mismatch`).
2. **Structured Logging**: A warning/error log is emitted containing the `request_id`, number of attempts, error types, and execution durations (with sensitive document contents redacted by default).
3. **Typed Exception**: The agent raises `StructuredOutputError`, containing the attempt count, the last encountered exception, and the history of diagnostic records.
4. **API Response**: The FastAPI layer translates this into an HTTP `422 Unprocessable Content` response containing machine-readable error details and the `request_id`.
5. **Operational Fallback**: Downstream orchestrators can inspect the `422` response to route the raw document to an asynchronous dead-letter queue (DLQ) or flag it for manual human review, ensuring that bad data is never silently written to transactional databases.
