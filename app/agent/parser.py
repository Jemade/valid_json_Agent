import json
import re
from typing import Any

from app.agent.exceptions import JSONParseError


class RobustJSONParser:
    """Parses JSON from raw LLM responses, handling common LLM formatting artifacts

    while rejecting invalid or fabricated structures.
    """

    # Matches markdown code blocks: ```json ... ``` or ``` ... ```
    CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)

    # Matches trailing commas before closing braces or brackets
    TRAILING_COMMA_PATTERN = re.compile(r",\s*([}\]])")

    # Matches single-quoted keys or values: 'key': 'val'
    SINGLE_QUOTE_PATTERN = re.compile(r"(?<=[\{\[\s,])'([^'\\]*(?:\\.[^'\\]*)*)'(?=\s*[:,\}\]])")

    def parse(self, raw_text: str) -> dict[str, Any]:
        """Extract and parse a JSON object from raw LLM output.

        Raises:
            JSONParseError: If no valid JSON object can be extracted.
        """
        if not raw_text or not raw_text.strip():
            raise JSONParseError("Empty response received from model", raw_snippet="")

        cleaned = raw_text.strip()

        # Step 1: Extract from markdown code fence if present
        code_block_match = self.CODE_BLOCK_PATTERN.search(cleaned)
        if code_block_match:
            cleaned = code_block_match.group(1).strip()

        # Step 2: Check if model returned an array instead of an object
        if cleaned.startswith("[") and cleaned.endswith("]"):
            raise JSONParseError(
                "Expected a JSON object ({...}), but received a JSON array ([...])",
                raw_snippet=cleaned[:200],
            )

        # Step 3: Extract JSON object boundaries
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")

        if first_brace == -1:
            raise JSONParseError(
                "No JSON object detected in model output (missing '{')",
                raw_snippet=cleaned[:200],
            )

        # Check for unclosed / truncated JSON (more opening braces than closing braces)
        if cleaned.count("{") > cleaned.count("}") or last_brace == -1 or last_brace < first_brace:
            raise JSONParseError(
                "Incomplete JSON output: opening '{' found without matching closing '}'",
                raw_snippet=cleaned[first_brace : first_brace + 200],
            )

        json_candidate = cleaned[first_brace : last_brace + 1].strip()

        # Step 4: Attempt direct parsing
        try:
            parsed = json.loads(json_candidate)
            if not isinstance(parsed, dict):
                raise JSONParseError(
                    f"Expected JSON object (dict), received {type(parsed).__name__}",
                    raw_snippet=json_candidate[:200],
                )
            return parsed
        except json.JSONDecodeError as direct_err:
            # Step 4: Attempt conservative repairs for known LLM quirks:
            # - Trailing commas: {"a": 1, }
            # - Single quotes: {'a': 1}
            repaired = self._attempt_repair(json_candidate)
            try:
                parsed = json.loads(repaired)
                if not isinstance(parsed, dict):
                    raise JSONParseError(
                        f"Expected JSON object (dict), received {type(parsed).__name__}",
                        raw_snippet=repaired[:200],
                    )
                return parsed
            except json.JSONDecodeError:
                raise JSONParseError(
                    f"Invalid JSON syntax: {direct_err.msg} at line {direct_err.lineno}, column {direct_err.colno}",
                    raw_snippet=json_candidate[:300],
                    line=direct_err.lineno,
                    column=direct_err.colno,
                ) from direct_err

    def _attempt_repair(self, text: str) -> str:
        """Applies conservative syntactic repairs for common LLM syntax slips."""
        # Remove trailing commas before } or ]
        repaired = self.TRAILING_COMMA_PATTERN.sub(r"\1", text)

        # Handle single-quoted keys and strings: 'key': 'val' -> "key": "val"
        if "'" in repaired and '"' not in repaired:
            # Text uses exclusively single quotes
            repaired = repaired.replace("'", '"')
        else:
            # Mixed quotes: replace single quotes around dictionary keys and simple values
            repaired = self.SINGLE_QUOTE_PATTERN.sub(r'"\1"', repaired)

        return repaired
