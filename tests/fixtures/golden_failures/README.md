# Golden Failure Fixtures & Expected Agent Behaviors

This directory contains real-world examples of malformed and invalid LLM outputs encountered when prompting models for structured JSON data. Each fixture documents the root cause, parser/validator behavior, and whether a retry should be triggered.

---

### 1. `01_markdown_wrapped.txt`
- **Why it is invalid**: LLMs frequently enclose JSON responses within Markdown code blocks (e.g. ```` ```json ... ``` ````). Strict `json.loads` fails immediately with `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`.
- **What should happen**: `RobustJSONParser` extracts the content between the markdown fences and parses the enclosed JSON without failing.
- **Whether retry should occur**: **No retry needed**. The parser successfully recovers the valid JSON payload directly.

---

### 2. `02_conversational_prefix.txt`
- **Why it is invalid**: Models often generate conversational preambles ("Here is the extracted invoice:") and postscripts ("I hope this helps!"). Standard JSON parsers fail because non-whitespace text precedes the opening `{`.
- **What should happen**: `RobustJSONParser` identifies the outer object boundaries (`{ ... }`) and isolates the JSON payload.
- **Whether retry should occur**: **No retry needed**. The parser isolates the valid object without consuming an attempt.

---

### 3. `03_unclosed_brace.txt`
- **Why it is invalid**: The model token limit was exceeded or the generation was truncated mid-stream, resulting in an opening `{` with no closing `}`.
- **What should happen**: `RobustJSONParser` detects an unclosed JSON structure and raises `JSONParseError("Incomplete JSON output: opening '{' found without matching closing '}'")`.
- **Whether retry should occur**: **Yes, retry should occur**. The agent constructs a corrective prompt notifying the model that its output was cut off and incomplete.

---

### 4. `04_single_quotes.txt`
- **Why it is invalid**: Models fine-tuned on Python or returning Python literal syntax output single quotes (`{'key': 'val'}`) instead of valid JSON double quotes.
- **What should happen**: `RobustJSONParser` applies a conservative quote normalization pass and parses the dictionary safely.
- **Whether retry should occur**: **No retry needed**. Handled syntactically by the parser.

---

### 5. `05_missing_required_total.json`
- **Why it is invalid**: The JSON is syntactically valid, but fails Pydantic schema validation because the required `total` field is missing.
- **What should happen**: `SchemaValidator` catches the `ValidationError`, categorizes it as `missing_field`, and raises `SchemaValidationError`.
- **Whether retry should occur**: **Yes, retry should occur**. The agent builds a corrective prompt specifying: `Field 'total': Field required` so the model supplies it on attempt 2.

---

### 6. `06_wrong_type_subtotal.json`
- **Why it is invalid**: The `subtotal` field contains a string `"five hundred dollars"` instead of a numeric `float`.
- **What should happen**: `SchemaValidator` detects `type_error` on `subtotal` and raises `SchemaValidationError`.
- **Whether retry should occur**: **Yes, retry should occur**. The corrective prompt informs the model that `subtotal` must be a valid float.

---

### 7. `07_math_mismatch_totals.json`
- **Why it is invalid**: Cross-field mathematical consistency fails: `subtotal` (500.0) + `tax` (50.0) != `total` (999.0).
- **What should happen**: Pydantic's `validate_invoice_totals_and_dates` model validator detects the arithmetic discrepancy and raises a `ValueError`.
- **Whether retry should occur**: **Yes, retry should occur**. The corrective prompt informs the model of the exact mismatch: `Total (999.00) does not match subtotal (500.00) + tax (50.00) = 550.00`.

---

### 8. `08_empty_line_items.json`
- **Why it is invalid**: The `line_items` array is empty `[]`, violating the `min_length=1` constraint on the invoice schema.
- **What should happen**: `SchemaValidator` flags `line_items` as a constraint violation.
- **Whether retry should occur**: **Yes, retry should occur**. The corrective prompt instructs the model to extract at least one line item from the document.
