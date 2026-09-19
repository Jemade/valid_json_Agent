from app.agent.exceptions import JSONParseError, SchemaValidationError


class PromptBuilder:
    """Constructs initial extraction prompts and targeted corrective prompts for retry attempts."""

    SYSTEM_PROMPT = (
        "You are an expert financial document extraction agent. "
        "Your task is to extract structured data from business documents with 100% precision. "
        "You must output ONLY a valid JSON object adhering strictly to the requested schema. "
        "Do not include conversational preamble, explanations, or markdown fences."
    )

    INVOICE_SCHEMA_INSTRUCTIONS = (
        "Schema Specification:\n"
        "- invoice_number (string, required): Invoice reference code\n"
        "- supplier (object, required): { name (string, required), tax_id (string, optional), address (string, optional), email (string, optional) }\n"
        "- customer (object, required): { name (string, required), tax_id (string, optional), address (string, optional), email (string, optional) }\n"
        "- invoice_date (string, required): Date in YYYY-MM-DD format\n"
        "- due_date (string, optional): Due date in YYYY-MM-DD format\n"
        "- currency (string, required): Three-letter code, e.g., 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF'\n"
        "- line_items (array of objects, at least 1 required): [{ description (string), quantity (float > 0), unit_price (float >= 0), total (float >= 0) }]\n"
        "  * For each line item: total must equal quantity * unit_price\n"
        "- subtotal (float, required): Must equal the sum of all line item totals\n"
        "- tax (float, required): Tax or VAT amount\n"
        "- total (float, required): Grand total, must exactly equal subtotal + tax\n"
    )

    def build_initial_prompt(self, document_text: str) -> str:
        """Construct the initial extraction prompt for a given document."""
        return (
            "Extract the invoice data from the document below into the exact JSON schema.\n\n"
            f"{self.INVOICE_SCHEMA_INSTRUCTIONS}\n"
            "Document Text:\n"
            "--------------------\n"
            f"{document_text.strip()}\n"
            "--------------------\n\n"
            "Output ONLY the JSON object."
        )

    def build_corrective_prompt(
        self,
        document_text: str,
        previous_output: str,
        error: Exception,
        attempt: int,
    ) -> str:
        """Construct a targeted corrective prompt explaining the exact validation failures."""
        if isinstance(error, JSONParseError):
            error_details = (
                f"JSON Parsing Error: {error.message}\nProblematic text snippet:\n```\n{error.raw_snippet}\n```"
            )
        elif isinstance(error, SchemaValidationError):
            error_lines = []
            for item in error.errors:
                field = item.get("field", "root")
                msg = item.get("message", "")
                recv = item.get("received")
                line = f"- Field '{field}': {msg}"
                if recv is not None:
                    line += f" (received: {recv})"
                error_lines.append(line)
            error_details = "Schema Validation Errors:\n" + "\n".join(error_lines)
        else:
            error_details = f"Validation Error: {str(error)}"

        return (
            f"Your previous response in attempt {attempt} was invalid and rejected by the validator.\n\n"
            f"{error_details}\n\n"
            f"{self.INVOICE_SCHEMA_INSTRUCTIONS}\n"
            "Correct the issues identified above. "
            "Ensure all required fields are present, types are correct, and all mathematical constraints hold "
            "(subtotal == sum(line_items.total), total == subtotal + tax, line_item.total == quantity * unit_price).\n\n"
            "Original Document Text:\n"
            "--------------------\n"
            f"{document_text.strip()}\n"
            "--------------------\n\n"
            "Return ONLY the corrected JSON object."
        )
