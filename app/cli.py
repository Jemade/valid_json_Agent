import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.agent.exceptions import ProviderError, StructuredOutputError
from app.agent.extractor import StructuredOutputAgent
from app.config import settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.mock_provider import MockProvider
from app.providers.openai_provider import OpenAIProvider
from app.schemas.invoice import Invoice


def create_provider(provider_name: str, model: str | None = None) -> LLMProvider:
    name = (provider_name or settings.default_provider).lower()
    if name == "mock":
        # By default in CLI mock mode, provide a valid invoice response if none queued
        default_mock_invoice = json.dumps(
            {
                "invoice_number": "INV-2024-001",
                "supplier": {"name": "Acme Corp", "email": "billing@acme.com"},
                "customer": {"name": "Global Tech Ltd", "address": "123 Innovation Way"},
                "invoice_date": "2024-03-15",
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Cloud Hosting Services",
                        "quantity": 1.0,
                        "unit_price": 500.0,
                        "total": 500.0,
                    }
                ],
                "subtotal": 500.0,
                "tax": 50.0,
                "total": 550.0,
            }
        )
        return MockProvider(responses=[default_mock_invoice], model=model or "mock-model")
    elif name == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=model or settings.default_model,
            timeout=settings.request_timeout_seconds,
        )
    elif name == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url,
            model=model or "claude-3-5-sonnet-20241022",
            timeout=settings.request_timeout_seconds,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


async def run_extract(args: argparse.Namespace) -> int:
    file_path = Path(args.filepath)
    if not file_path.is_file():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    document_text = file_path.read_text(encoding="utf-8")
    try:
        provider = create_provider(args.provider, args.model)
    except ValueError as err:
        print(f"Configuration error: {err}", file=sys.stderr)
        return 1

    agent = StructuredOutputAgent(
        provider=provider,
        max_retries=args.max_retries,
        log_raw_input=settings.log_raw_input,
        log_raw_output=settings.log_raw_output,
    )

    print(f"Processing document: {file_path.name}")
    print(f"Provider: {args.provider} | Max retries: {args.max_retries}")

    try:
        result = await agent.extract(document_text=document_text, model_cls=Invoice)
        print("\n--- EXTRACTION SUCCESSFUL ---")
        print(f"Attempts: {result.attempts}")
        print(f"Request ID: {result.request_id}")
        print(f"Duration: {result.duration_ms:.1f}ms")
        print("\nStructured Data:")
        print(json.dumps(result.data.model_dump(mode="json"), indent=2))
        return 0

    except StructuredOutputError as exc:
        print("\n--- EXTRACTION FAILED (Retry Budget Exhausted) ---", file=sys.stderr)
        if exc.last_error and hasattr(exc.last_error, "errors"):
            print("Validation Details:", file=sys.stderr)
            error_items = getattr(exc.last_error, "errors", [])
            for item in error_items:
                print(f"  - [{item.get('field')}]: {item.get('message')}", file=sys.stderr)
        return 1

    except ProviderError as exc:
        print(f"\n--- PROVIDER ERROR ---\n{exc.message}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="structured-agent",
        description="Structured Output Agent CLI for document extraction",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract", help="Extract structured data from a document")
    extract_parser.add_argument("filepath", type=str, help="Path to text document")
    extract_parser.add_argument(
        "--provider",
        type=str,
        default="mock",
        choices=["mock", "openai", "anthropic"],
        help="LLM provider adapter (default: mock)",
    )
    extract_parser.add_argument("--model", type=str, default=None, help="LLM model identifier")
    extract_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)",
    )

    args = parser.parse_args()
    if args.command == "extract":
        sys.exit(asyncio.run(run_extract(args)))


if __name__ == "__main__":
    main()
