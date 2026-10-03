# JSON and invoice failure fixtures

Small fixtures used to exercise JSON recovery and invoice validation.

| Fixture | Case | Expected treatment |
| --- | --- | --- |
| `01_markdown_wrapped.txt` | JSON inside a Markdown fence | Extract and parse the payload |
| `02_conversational_prefix.txt` | Text around a JSON object | Isolate the object |
| `03_unclosed_brace.txt` | Truncated object | Reject and request a correction |
| `04_single_quotes.txt` | Python-style quoted object | Apply supported conservative recovery |
| `05_missing_required_total.json` | Missing total | Reject through schema validation |
| `06_wrong_type_subtotal.json` | Non-numeric subtotal | Reject through schema validation |
| `07_math_mismatch_totals.json` | Inconsistent arithmetic | Reject through invoice validation |
| `08_empty_line_items.json` | Empty line-item list | Reject through schema validation |

Recovery handles supported formatting problems. It does not supply missing business values. Corrections are bounded by the configured retry budget.

Run `pytest -q` from the repository root for the regression checks. Implementation lives in `app/agent/` and `app/schemas/`.
