import time
from typing import Any

from app.agent.exceptions import ProviderError
from app.providers.base import ProviderResponse


class MockProvider:
    """Deterministic mock provider for unit tests and local demonstrations."""

    def __init__(
        self,
        responses: list[str | Exception] | None = None,
        model: str = "mock-model",
    ):
        self.responses: list[str | Exception] = list(responses or [])
        self.model = model
        self.provider_name = "mock"
        self.call_history: list[dict[str, Any]] = []

    def queue_response(self, response: str | Exception) -> None:
        """Enqueue a simulated response or exception."""
        self.responses.append(response)

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        start_time = time.perf_counter()

        self.call_history.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "call_index": len(self.call_history),
            }
        )

        if not self.responses:
            raise ProviderError(
                message="MockProvider response queue is empty",
                provider=self.provider_name,
            )

        item = self.responses.pop(0)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if isinstance(item, Exception):
            raise item

        return ProviderResponse(
            content=item,
            model=self.model,
            provider_name=self.provider_name,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(item.split()),
            latency_ms=duration_ms,
        )
