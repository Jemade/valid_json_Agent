import time

import httpx

from app.agent.exceptions import ProviderError, ProviderTimeoutError
from app.providers.base import ProviderResponse


class AnthropicProvider:
    """Adapter for Anthropic Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com/v1",
        model: str = "claude-3-5-sonnet-20241022",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.provider_name = "anthropic"

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(
                message="Anthropic API key is not configured. Set ANTHROPIC_API_KEY environment variable.",
                provider=self.provider_name,
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.0,
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract text from content blocks
            content_blocks = data.get("content", [])
            content = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
            usage = data.get("usage", {})

            return ProviderResponse(
                content=content,
                model=self.model,
                provider_name=self.provider_name,
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
                latency_ms=latency_ms,
            )

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                message=f"Anthropic request timed out after {self.timeout}s",
                provider=self.provider_name,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                message=f"Anthropic API returned error status {exc.response.status_code}: {exc.response.text}",
                provider=self.provider_name,
                status_code=exc.response.status_code,
            ) from exc
        except Exception as exc:
            raise ProviderError(
                message=f"Unexpected error communicating with Anthropic: {str(exc)}",
                provider=self.provider_name,
            ) from exc
