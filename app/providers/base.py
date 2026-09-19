from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResponse:
    content: str
    model: str
    provider_name: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float = 0.0


class LLMProvider(Protocol):
    """Protocol for LLM provider adapters."""

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        """Send a completion request to the LLM provider."""
        ...
